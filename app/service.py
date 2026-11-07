"""Une fonte de dados, validadores e motor quantitativo no que a API devolve.

Todo número daqui vem da fonte ou é calculado dela. Quando falta dado, o campo fica
None ou a função levanta DataInsufficientError: nunca há valor de reserva.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from core.calendario_b3 import trading_days_between
from quant.costs import CostSchedule
from core.clock import MARKET_TZ, market_today
from core.config import DataQualityLimits
from core.exceptions import DataInsufficientError
from core.text import decimal_comma
from core.types import CorporateEvent, MarketRegime, MarketSnapshot, OptionChain, OptionKind, OptionQuote, PriceBar, Provenance, SourceKind
from data.providers.base import DataProvider
from data.validators import ValidationReport, validate_bars, validate_chain, validate_snapshot
from quant.greeks import position_greeks
from quant.iv_rank import HIGH_RANK, LOW_RANK, MIN_SAMPLES, iv_rank
from quant.open_interest import summarize_open_interest
from quant.payoff import net_premium, payoff_curve
from quant.probability import probability_itm
from quant.regime import classify_regime
from quant.risk import CapitalLimits, RiskLimits, assess_risk, decide, pnl_heatmap, position_pop
from quant.structure import analyze_structure
from quant.strategies import CHEAP_IV_RATIO, RICH_IV_RATIO, build_candidates, fits_regime
from quant.volatility import bollinger_bands, ewma_volatility, historical_volatility, rolling_volatility

# Vencimento de referência do scanner: evita o gama dos últimos dias.
_MIN_REFERENCE_DAYS = 14
_BIG_MOVE = 3.0
_SCANNER_WORKERS = 4
_CHART_BARS = 120
# Um ano de amostras semanais. Cada amostra nova custa chamadas à fonte: as que não couberem
# neste tempo ficam para a próxima varredura, e as já guardadas não são buscadas de novo.
_IV_HISTORY_WEEKS = 52
_IV_SECONDS_PER_SYMBOL = 6.0
# Janelas de alerta: rompimento recente e evento próximo.
_RECENT_STRUCTURE_BARS = 3
_SOON_EVENT_DAYS = 7
# Abaixo do limite de 60 s da função: cada chamada à fonte leva até 20 s (duas tentativas).
_SCAN_BUDGET_SECONDS = 35.0
_TIMED_OUT = "Varredura: tempo esgotado antes de analisar este ativo"


def data_status(price: float | None, market_time: str | None, missing: list[str], now: datetime) -> str:
    """REAL: cotação na janela de atraso e tudo completo. Nunca é inferido da falta de erro."""
    if price is None or market_time is None:
        return "INDISPONIVEL"
    if missing:
        return "INCOMPLETO"
    age = (now - datetime.fromisoformat(market_time)).total_seconds()
    return "ATRASADO" if age > DataQualityLimits().max_age_seconds else "REAL"


def _provenance(provenance: Provenance) -> dict:
    return {
        "source": provenance.source,
        "kind": provenance.kind.value,
        "collected_at": provenance.collected_at.isoformat(),
        "market_time": provenance.market_time.isoformat(),
    }


def _report(report: ValidationReport) -> dict:
    return {
        "is_valid": report.is_valid,
        "issues": [{"code": i.code, "severity": i.severity.value, "detail": i.detail} for i in report.issues],
    }


def _snapshot(snapshot: MarketSnapshot) -> dict:
    return {
        "symbol": snapshot.symbol,
        "name": snapshot.name,
        "price": snapshot.price,
        "change_percent": snapshot.change_percent,
        "volume": snapshot.volume,
        "provenance": _provenance(snapshot.provenance),
    }


def _volatility(bars: list[PriceBar]) -> tuple[float | None, float | None]:
    closes = [bar.close for bar in bars]
    try:
        return historical_volatility(closes), ewma_volatility(closes)
    except DataInsufficientError:
        return None, None


def _regime(bars: list[PriceBar], iv_ratio: float | None) -> MarketRegime | None:
    try:
        return classify_regime([bar.close for bar in bars], iv_ratio)
    except DataInsufficientError:
        return None


def _atm_iv(quotes: tuple[OptionQuote, ...], spot: float) -> float | None:
    """Média da call e da put mais próximas do ativo que tenham volatilidade."""
    values = []
    for kind in (OptionKind.CALL, OptionKind.PUT):
        with_iv = [quote for quote in quotes if quote.kind is kind and quote.iv]
        if with_iv:
            values.append(min(with_iv, key=lambda quote: abs(quote.strike - spot)).iv)
    return sum(values) / len(values) if values else None


def _reference_expiry(expirations: list[date], today: date) -> date | None:
    limit = today + timedelta(days=_MIN_REFERENCE_DAYS)
    return min((day for day in expirations if day >= limit), default=None)


def spot_drift(chain: OptionChain, live: MarketSnapshot | None) -> float | None:
    """None = não medida. Cotação de fim de dia do mesmo pregão da grade é o próprio preço da grade:
    daria sempre 0%, escondendo qualquer movimento desde então."""
    if live is None:
        return None
    if live.provenance.kind is SourceKind.EOD and chain.market_date and (
        live.provenance.market_time.astimezone(MARKET_TZ).date() <= chain.market_date
    ):
        return None
    return live.price / chain.underlying.price - 1


def _try_snapshot(provider: DataProvider, symbol: str) -> MarketSnapshot | None:
    try:
        return provider.get_market_snapshot(symbol)
    except DataInsufficientError:
        return None


def _try_events(provider: DataProvider, symbol: str, today: date) -> tuple[list[CorporateEvent], str | None]:
    """Falha no calendário não derruba a análise, mas precisa aparecer: ausência não é "sem evento"."""
    try:
        return provider.get_upcoming_events(symbol, today), None
    except DataInsufficientError as error:
        return [], error.detail


def _try_bars(provider: DataProvider, symbol: str) -> list[PriceBar]:
    try:
        bars = provider.get_historical_prices(symbol)
    except DataInsufficientError:
        return []
    return bars if validate_bars(bars).is_valid else []


def _structure_view(bars: list[PriceBar]) -> dict | None:
    if not bars:
        return None
    result = analyze_structure(bars)
    first_visible = max(0, len(bars) - _CHART_BARS)
    return {
        "trend": result.trend,
        "last_swing_high": result.last_swing_high,
        "last_swing_low": result.last_swing_low,
        "events": [
            {"day": event.day, "kind": event.kind, "direction": event.direction, "level": event.level}
            for event in result.events
            if event.bar_index >= first_visible
        ],
    }


def _events_view(events: list[CorporateEvent]) -> list[dict]:
    return [
        {"kind": event.kind, "day": event.day.isoformat(), "label": event.label, "confirmed": event.confirmed}
        for event in events
    ]


def _chart_bars(bars: list[PriceBar]) -> list[dict]:
    closes = [bar.close for bar in bars]
    hv = rolling_volatility(closes)
    bands = bollinger_bands(closes)
    points = [
        {
            "day": bar.day.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "hv_20d": hv[index],
            "bb_upper": bands[index][0] if bands[index] else None,
            "bb_middle": bands[index][1] if bands[index] else None,
            "bb_lower": bands[index][2] if bands[index] else None,
        }
        for index, bar in enumerate(bars)
    ]
    return points[-_CHART_BARS:]


def asset_overview(provider: DataProvider, symbol: str, now: datetime) -> dict:
    snapshot = provider.get_market_snapshot(symbol)
    bars = provider.get_historical_prices(symbol)
    bars_report = validate_bars(bars)
    usable_bars = bars if bars_report.is_valid else []
    hv, ewma = _volatility(usable_bars)
    regime = _regime(usable_bars, None)
    return {
        "quote": _snapshot(snapshot),
        "quote_quality": _report(validate_snapshot(snapshot, now)),
        "data_status": data_status(snapshot.price, snapshot.provenance.market_time.isoformat(), [], now),
        "history_quality": _report(bars_report),
        "historical_volatility": hv,
        "ewma_volatility": ewma,
        "regime": regime.value if regime else None,
        "history": _chart_bars(usable_bars),
        "structure": _structure_view(usable_bars),
    }


def _load_chain(provider: DataProvider, symbol: str, expiry: date, now: datetime) -> tuple[OptionChain, ValidationReport]:
    chain = provider.get_option_chain(symbol, expiry)
    report = validate_chain(chain, now)
    report.require_valid()
    return chain, report


def chain_view(provider: DataProvider, symbol: str, expiry: date, now: datetime) -> dict:
    chain, report = _load_chain(provider, symbol, expiry, now)
    usable = {quote.symbol for quote in report.usable_quotes}
    return {
        "symbol": symbol,
        "expiry": expiry.isoformat(),
        "market_date": chain.market_date.isoformat() if chain.market_date else None,
        "spot": chain.underlying.price,
        "risk_free_rate": chain.risk_free_rate,
        "provenance": _provenance(chain.underlying.provenance),
        "quality": _report(report),
        "open_interest": summarize_open_interest(chain.quotes).__dict__,
        "quotes": [
            {
                "symbol": quote.symbol,
                "kind": quote.kind.value,
                "strike": quote.strike,
                "style": quote.style.value if quote.style else None,
                "bid": quote.bid or None,
                "ask": quote.ask or None,
                "close": quote.close,
                "open_interest": quote.open_interest,
                "volume": quote.volume,
                "trades": quote.trades,
                "iv": quote.iv,
                "delta": quote.delta,
                "usable": quote.symbol in usable,
            }
            for quote in sorted(chain.quotes, key=lambda item: (item.strike, item.kind.value))
        ],
    }


def strategies_view(
    provider: DataProvider,
    symbol: str,
    expiry: date,
    now: datetime,
    limits: RiskLimits = RiskLimits(),
    profile: str | None = None,
    capital: CapitalLimits | None = None,
    costs: CostSchedule | None = None,
) -> dict:
    chain, report = _load_chain(provider, symbol, expiry, now)
    if chain.risk_free_rate is None or chain.time_to_expiry_years is None:
        raise DataInsufficientError(f"{symbol}: a fonte não informou taxa de juros e prazo da grade")
    spot, t, r = chain.underlying.price, chain.time_to_expiry_years, chain.risk_free_rate

    live = _try_snapshot(provider, symbol)
    drift = spot_drift(chain, live)
    bars = _try_bars(provider, symbol)
    hv, _ = _volatility(bars)
    atm_iv = _atm_iv(report.usable_quotes, spot)
    iv_ratio = atm_iv / hv if atm_iv and hv else None
    regime = _regime(bars, iv_ratio)

    use_book = chain.market_date is None
    candidates, unavailable = build_candidates(report.usable_quotes, spot, use_book=use_book, profile=profile)
    events, events_error = _try_events(provider, symbol, market_today(now))
    rank_row: dict = {"missing": [], "iv_rank": None, "iv_percentile": None, "iv_samples": 0}
    if chain.market_date:
        _fill_iv_rank(provider, symbol, chain.market_date, rank_row)
    rows = []
    for candidate in candidates:
        proposal = candidate.proposal
        ivs = [quote.iv for quote in candidate.quotes]
        risk = assess_risk(
            proposal, candidate.quotes, spot, t, r, drift, limits, use_book, events=events, today=now.date()
        )
        greeks = position_greeks(proposal.legs, ivs, spot, t, r)
        rows.append(
            {
                "key": candidate.key,
                "name": proposal.name,
                "rationale": proposal.rationale,
                "assumptions": proposal.assumptions,
                "fits_regime": fits_regime(candidate.key, regime, iv_ratio),
                "net_premium": net_premium(proposal.legs),
                "max_profit": proposal.max_profit,
                "max_loss": proposal.max_loss,
                "breakevens": proposal.breakeven_points,
                "risk_reward": proposal.risk_reward_ratio,
                "probability_of_profit": position_pop(proposal.legs, ivs, spot, t, r),
                "greeks": greeks.__dict__ if greeks else None,
                "legs": [
                    {
                        "symbol": leg.symbol,
                        "action": leg.action.value,
                        "kind": leg.kind.value,
                        "strike": leg.strike,
                        "quantity": leg.quantity,
                        "premium": leg.premium,
                        "price_basis": basis.value,
                        "iv": quote.iv,
                        "delta": quote.delta,
                        "style": quote.style.value if quote.style else None,
                        "probability_itm": probability_itm(leg.kind, spot, leg.strike, t, r, quote.iv),
                    }
                    for leg, basis, quote in zip(proposal.legs, candidate.bases, candidate.quotes)
                ],
                "risk": {
                    "is_approved": risk.is_approved,
                    "liquidity_score": risk.liquidity_score,
                    "stress": risk.stress_test_results,
                    "warnings": risk.warnings,
                    "verdict": risk.final_verdict,
                    "rejection_reason": risk.rejection_reason,
                },
                "payoff": [{"price": price, "pnl": pnl} for price, pnl in payoff_curve(proposal.legs, spot)],
                "heatmap": pnl_heatmap(proposal.legs, ivs, spot, t, r, [quote.style for quote in candidate.quotes]),
                "decision": decide(proposal, risk, capital, drift, costs),
            }
        )
    rows.sort(
        key=lambda row: (
            not row["risk"]["is_approved"],
            not row["fits_regime"],
            -(row["risk_reward"] or 0),
        )
    )
    return {
        "symbol": symbol,
        "expiry": expiry.isoformat(),
        "market_date": chain.market_date.isoformat() if chain.market_date else None,
        "spot": spot,
        "source": chain.underlying.provenance.source,
        "live_price": live.price if live else None,
        "spot_drift": drift,
        "risk_free_rate": r,
        "time_to_expiry_years": t,
        "business_days_to_expiry": trading_days_between(chain.market_date or market_today(now), expiry),
        "atm_iv": atm_iv,
        "historical_volatility": hv,
        "iv_ratio": iv_ratio,
        "regime": regime.value if regime else None,
        "profile": profile,
        "capital_configured": capital is not None,
        "costs_configured": costs is not None,
        "iv_rank": rank_row["iv_rank"],
        "iv_percentile": rank_row["iv_percentile"],
        "iv_samples": rank_row["iv_samples"],
        "iv_samples_needed": MIN_SAMPLES,
        "structure": _structure_view(bars),
        "events": _events_view(events),
        "events_error": events_error,
        "quality": _report(report),
        "candidates": rows,
        "unavailable": [item.__dict__ for item in unavailable],
    }


def _signals(row: dict, limits: RiskLimits) -> list[dict]:
    signals = []
    ratio = row["iv_ratio"]
    if ratio is not None:
        if ratio >= RICH_IV_RATIO:
            signals.append({"type": "VOL_CARA", "detail": f"Vol implícita {decimal_comma(f'{ratio:.2f}')}x a histórica."})
        elif ratio <= CHEAP_IV_RATIO:
            signals.append({"type": "VOL_BARATA", "detail": f"Vol implícita {decimal_comma(f'{ratio:.2f}')}x a histórica."})
    if row["change_percent"] is not None and abs(row["change_percent"]) >= _BIG_MOVE:
        signals.append({"type": "MOVIMENTO", "detail": f"Ativo {decimal_comma(format(row['change_percent'], '+.2f'))}% no dia."})
    if row["spot_drift"] is not None and abs(row["spot_drift"]) > limits.max_spot_drift:
        signals.append(
            {"type": "GRADE_DEFASADA", "detail": f"Ativo {decimal_comma(format(row['spot_drift'], '+.1%'))} desde o pregão da grade."}
        )
    rank = row["iv_rank"]
    if rank is not None and rank >= HIGH_RANK:
        signals.append({"type": "IV_RANK_ALTO", "detail": f"IV Rank {rank:.0f}: vol perto da máxima de 1 ano."})
    elif rank is not None and rank <= LOW_RANK:
        signals.append({"type": "IV_RANK_BAIXO", "detail": f"IV Rank {rank:.0f}: vol perto da mínima de 1 ano."})
    return signals


def _fill_iv_rank(
    provider: DataProvider, symbol: str, market_date: date, row: dict, stop_at: float | None = None
) -> None:
    """Sem dados suficientes, os campos ficam nulos e a tela mostra quantas amostras já existem."""
    current = None
    history: list[float] = []
    deadline = time.monotonic() + _IV_SECONDS_PER_SYMBOL
    if stop_at is not None:
        deadline = min(deadline, stop_at)
    try:
        current = provider.get_atm_iv_on(symbol, market_date)
        for week in range(1, _IV_HISTORY_WEEKS + 1):
            if time.monotonic() > deadline:
                break
            sample = provider.get_atm_iv_on(symbol, market_date - timedelta(weeks=week))
            if sample:
                history.append(sample.iv)
    except DataInsufficientError as error:
        # Limite da fonte, por exemplo: o que já foi guardado fica, e a próxima varredura continua.
        row["missing"].append(f"IV Rank: {error.detail}")
    row["iv_samples"] = len(history)
    if current is None:
        return
    try:
        result = iv_rank(current.iv, history)
    except DataInsufficientError:
        return
    row.update(iv_rank=result.rank, iv_percentile=result.percentile)


def scan_symbol(
    provider: DataProvider,
    symbol: str,
    now: datetime,
    limits: RiskLimits = RiskLimits(),
    stop_at: float | None = None,
) -> dict:
    row: dict = {
        "symbol": symbol,
        "name": None,
        "price": None,
        "change_percent": None,
        "market_time": None,
        "historical_volatility": None,
        "atm_iv": None,
        "iv_ratio": None,
        "regime": None,
        "expiry": None,
        "market_date": None,
        "spot_drift": None,
        "iv_rank": None,
        "iv_percentile": None,
        "iv_samples": 0,
        "iv_samples_needed": MIN_SAMPLES,
        "structure_trend": None,
        "events": [],
        "source": None,
        "data_status": "INDISPONIVEL",
        "missing": [],
        "history_warnings": [],
    }
    if stop_at is not None and time.monotonic() >= stop_at:
        row["missing"].append(_TIMED_OUT)
        row["signals"] = []
        return row
    live = None
    try:
        live = provider.get_market_snapshot(symbol)
        row.update(
            name=live.name,
            price=live.price,
            change_percent=live.change_percent,
            market_time=live.provenance.market_time.isoformat(),
            source=live.provenance.source,
        )
    except DataInsufficientError as error:
        row["missing"].append(f"Cotação: {error.detail}")

    bars: list[PriceBar] = []
    try:
        bars = provider.get_historical_prices(symbol)
        report = validate_bars(bars)
        report.require_valid()
        row["historical_volatility"], _ = _volatility(bars)
        row["history_warnings"] = [issue.detail for issue in report.issues if issue.code == "LARGE_JUMP"]
        if not all(bar.adjusted for bar in bars):
            row["history_warnings"].append("Histórico oficial da B3, sem ajuste de proventos: a vol histórica pode sair um pouco maior.")
    except DataInsufficientError as error:
        bars = []
        row["missing"].append(f"Histórico: {error.detail}")

    try:
        expiry = _reference_expiry(provider.get_expirations(symbol), market_today(now))
        if expiry is None:
            raise DataInsufficientError("sem vencimento a partir de 14 dias")
        chain, report = _load_chain(provider, symbol, expiry, now)
        row.update(
            expiry=expiry.isoformat(),
            market_date=chain.market_date.isoformat() if chain.market_date else None,
            atm_iv=_atm_iv(report.usable_quotes, chain.underlying.price),
            spot_drift=spot_drift(chain, live),
        )
        if chain.market_date:
            _fill_iv_rank(provider, symbol, chain.market_date, row, stop_at)
    except DataInsufficientError as error:
        row["missing"].append(f"Opções: {error.detail}")

    if row["atm_iv"] and row["historical_volatility"]:
        row["iv_ratio"] = row["atm_iv"] / row["historical_volatility"]
    regime = _regime(bars, row["iv_ratio"])
    row["regime"] = regime.value if regime else None
    events, events_error = _try_events(provider, symbol, market_today(now))
    row["events"] = _events_view(events)
    if events_error:
        row["missing"].append(f"Eventos: {events_error}")
    row["signals"] = _signals(row, limits) + [
        {"type": "SALTO_HISTORICO", "detail": detail} for detail in row["history_warnings"]
    ]
    limit = market_today(now) + timedelta(days=_SOON_EVENT_DAYS)
    for event in events:
        if event.kind == "RESULTADO" and event.day <= limit:
            status = "" if event.confirmed else " (data estimada)"
            row["signals"].append(
                {"type": "EVENTO_PROXIMO", "detail": f"{event.label} em {event.day.strftime('%d/%m/%Y')}{status}."}
            )
    if bars:
        structure = analyze_structure(bars)
        row["structure_trend"] = structure.trend
        if structure.events and structure.events[-1].bar_index >= len(bars) - _RECENT_STRUCTURE_BARS:
            last = structure.events[-1]
            side = "alta" if last.direction == "UP" else "baixa"
            level = decimal_comma(f"{last.level:.2f}")
            row["signals"].append(
                {"type": "ROMPIMENTO", "detail": f"{last.kind} de {side}: fechou além de {level} em {last.day}."}
            )
    row["data_status"] = data_status(row["price"], row["market_time"], row["missing"], now)
    return row


def _scan_safely(provider: DataProvider, symbol: str, now: datetime, stop_at: float) -> dict:
    try:
        return scan_symbol(provider, symbol, now, stop_at=stop_at)
    except Exception as error:  # noqa: BLE001 - uma falha não pode invalidar a coleta dos outros ativos.
        return {
            "symbol": symbol,
            "name": None,
            "price": None,
            "change_percent": None,
            "market_time": None,
            "historical_volatility": None,
            "atm_iv": None,
            "iv_ratio": None,
            "regime": None,
            "expiry": None,
            "market_date": None,
            "spot_drift": None,
            "iv_rank": None,
            "iv_percentile": None,
            "iv_samples": 0,
            "iv_samples_needed": MIN_SAMPLES,
            "structure_trend": None,
            "events": [],
            "source": None,
            "data_status": "INDISPONIVEL",
            "missing": [f"Ativo: falha inesperada ({type(error).__name__})"],
            "history_warnings": [],
            "signals": [],
        }


def scanner(
    provider: DataProvider, symbols: list[str], now: datetime, budget_seconds: float = _SCAN_BUDGET_SECONDS
) -> dict:
    """Um ativo sem dados aparece com o motivo, sem derrubar os demais.

    `complete` só é verdadeiro se todos os ativos foram analisados por inteiro.
    """
    stop_at = time.monotonic() + budget_seconds
    with ThreadPoolExecutor(max_workers=_SCANNER_WORKERS) as pool:
        rows = list(pool.map(lambda symbol: _scan_safely(provider, symbol, now, stop_at), symbols))
    timed_out = [row["symbol"] for row in rows if _TIMED_OUT in row["missing"]]
    incomplete = [row["symbol"] for row in rows if row["missing"]]
    return {
        "generated_at": now.isoformat(),
        "rows": rows,
        "complete": not incomplete,
        "incomplete_symbols": incomplete,
        "timed_out_symbols": timed_out,
    }
