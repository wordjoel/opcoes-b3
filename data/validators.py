"""Qualidade de dados: nenhum número entra nos motores sem passar por aqui.

O horário de referência (`now`) é sempre explícito, para o resultado ser
reproduzível. Problemas em uma só cotação geram aviso e a excluem da lista de
utilizáveis; problemas que comprometem a análise inteira tornam o relatório inválido.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from core.config import DataQualityLimits
from core.exceptions import DataInsufficientError
from core.text import decimal_comma
from core.types import MarketSnapshot, OptionChain, OptionKind, OptionQuote, PriceBar, Provenance, SourceKind


class Severity(str, Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[Issue, ...] = ()
    usable_quotes: tuple[OptionQuote, ...] = field(default=())

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity is Severity.ERROR for issue in self.issues)

    @property
    def codes(self) -> set[str]:
        return {issue.code for issue in self.issues}

    def require_valid(self) -> None:
        if not self.is_valid:
            errors = [i.detail for i in self.issues if i.severity is Severity.ERROR]
            raise DataInsufficientError("dados recusados na validação", errors)


def _error(code: str, detail: str) -> Issue:
    return Issue(code, Severity.ERROR, detail)


def _warning(code: str, detail: str) -> Issue:
    return Issue(code, Severity.WARNING, detail)


def _check_provenance(
    label: str, provenance: Provenance, now: datetime, limits: DataQualityLimits, allow_test: bool
) -> list[Issue]:
    issues: list[Issue] = []
    if provenance.kind is SourceKind.TEST and not allow_test:
        issues.append(_error("TEST_DATA", f"{label}: dado de teste recusado"))
    age = (now - provenance.market_time).total_seconds()
    max_age = limits.max_eod_age_seconds if provenance.kind is SourceKind.EOD else limits.max_age_seconds
    if age > max_age:
        issues.append(_error("DATA_STALE", f"{label}: dado com {age:.0f}s de idade"))
    if age < -limits.max_future_seconds:
        issues.append(_error("FUTURE_TIMESTAMP", f"{label}: horário {-age:.0f}s no futuro"))
    return issues


def validate_snapshot(
    snapshot: MarketSnapshot,
    now: datetime,
    limits: DataQualityLimits = DataQualityLimits(),
    allow_test: bool = False,
) -> ValidationReport:
    return ValidationReport(tuple(_check_provenance(snapshot.symbol, snapshot.provenance, now, limits, allow_test)))


def _quote_problem(quote: OptionQuote, spot: float, now: datetime, market_date: date | None) -> Issue | None:
    label = quote.symbol
    if market_date is not None and quote.last_trade_date != market_date:
        return _warning("NOT_TRADED", f"{label}: sem negócio no pregão de {market_date}")
    # Em grade de fim de dia, bid e ask são sobras de ofertas após o fechamento, sem valor
    # de preço: a PETRL497 negociou 607.600 opções em 30/10 e fechou com 0,25 x 18,50.
    if market_date is not None:
        if not quote.close:
            return _warning("MISSING_QUOTE", f"{label}: sem preço de fechamento")
        price = quote.close
    else:
        if not quote.bid or not quote.ask:
            return _warning("MISSING_QUOTE", f"{label}: sem bid e ask")
        if quote.bid > quote.ask:
            return _warning("CROSSED_QUOTE", f"{label}: bid {quote.bid} acima do ask {quote.ask}")
        price = quote.bid
    if quote.expiry < now.date():
        return _warning("EXPIRED_OPTION", f"{label}: venceu em {quote.expiry}")
    # O prêmio de uma call nunca excede o ativo, nem o de uma put europeia, o strike.
    if quote.kind is OptionKind.CALL and price > spot:
        return _warning("PRICE_OUTLIER", f"{label}: preço acima do ativo")
    if quote.kind is OptionKind.PUT and price > quote.strike:
        return _warning("PRICE_OUTLIER", f"{label}: preço acima do strike")
    return None


def validate_chain(
    chain: OptionChain,
    now: datetime,
    limits: DataQualityLimits = DataQualityLimits(),
    allow_test: bool = False,
) -> ValidationReport:
    spot = chain.underlying
    issues = _check_provenance(spot.symbol, spot.provenance, now, limits, allow_test)
    if not chain.quotes:
        issues.append(_error("EMPTY_CHAIN", f"{spot.symbol}: grade sem opções"))
        return ValidationReport(tuple(issues))

    usable: list[OptionQuote] = []
    for quote in chain.quotes:
        if quote.underlying != spot.symbol:
            issues.append(_error("UNDERLYING_MISMATCH", f"{quote.symbol}: pertence a {quote.underlying}"))
            continue
        quote_issues = _check_provenance(quote.symbol, quote.provenance, now, limits, allow_test)
        skew = abs((quote.provenance.market_time - spot.provenance.market_time).total_seconds())
        if skew > limits.max_time_skew_seconds:
            quote_issues.append(_error("TIME_SKEW", f"{quote.symbol}: {skew:.0f}s de diferença para o ativo"))
        issues.extend(quote_issues)
        problem = _quote_problem(quote, spot.price, now, chain.market_date)
        if problem is not None:
            issues.append(problem)
        elif not quote_issues:
            usable.append(quote)

    if usable and chain.market_date is not None:
        issues.append(_warning("CLOSE_ONLY", f"{len(usable)} opções com preço indicativo pelo fechamento"))
    if not usable:
        issues.append(_error("NO_USABLE_QUOTES", f"{spot.symbol}: nenhuma opção utilizável"))
    return ValidationReport(tuple(issues), tuple(usable))


def validate_bars(bars: list[PriceBar], limits: DataQualityLimits = DataQualityLimits()) -> ValidationReport:
    """Série histórica ordenada, coerente e de um único ativo."""
    issues: list[Issue] = []
    if not bars:
        return ValidationReport((_error("EMPTY_SERIES", "série histórica vazia"),))
    if len({bar.symbol for bar in bars}) > 1:
        issues.append(_error("MIXED_SYMBOLS", "série mistura ativos"))
    if len({bar.adjusted for bar in bars}) > 1:
        issues.append(_error("MIXED_ADJUSTMENT", "série mistura preços ajustados e não ajustados"))
    for bar in bars:
        if bar.low > bar.high or not bar.low <= bar.close <= bar.high or not bar.low <= bar.open <= bar.high:
            issues.append(_error("INCONSISTENT_BAR", f"{bar.symbol} {bar.day}: OHLC incoerente"))
    for previous, current in zip(bars, bars[1:]):
        gap = (current.day - previous.day).days
        if gap <= 0:
            issues.append(_error("UNORDERED_SERIES", f"{current.day}: data fora de ordem ou repetida"))
        elif gap > limits.max_bar_gap_days:
            issues.append(_warning("SERIES_GAP", f"{gap} dias sem dados até {current.day}"))
        move = current.close / previous.close - 1
        if abs(move) > limits.max_daily_move:
            issues.append(
                _warning(
                    "LARGE_JUMP",
                    f"{current.day.strftime('%d/%m/%Y')}: fechamento de "
                    + decimal_comma(f"{previous.close:.2f} para {current.close:.2f}")
                    + f" ({move:+.0%}) em um pregão. Confira se é fato de mercado ou erro da fonte; "
                    "a volatilidade histórica inclui esse salto.",
                )
            )
    return ValidationReport(tuple(issues))


def compare_sources(
    first: MarketSnapshot, second: MarketSnapshot, limits: DataQualityLimits = DataQualityLimits()
) -> ValidationReport:
    """Duas fontes para o mesmo ativo: divergência impede escolher uma em silêncio."""
    issues: list[Issue] = []
    skew = abs((first.provenance.market_time - second.provenance.market_time).total_seconds())
    if skew > limits.max_time_skew_seconds:
        issues.append(_error("TIME_SKEW", f"{first.symbol}: {skew:.0f}s entre as fontes"))
    divergence = abs(first.price - second.price) / min(first.price, second.price)
    if divergence > limits.max_source_divergence:
        issues.append(
            _error(
                "SOURCE_DIVERGENCE",
                f"{first.symbol}: {first.provenance.source}={first.price} e "
                f"{second.provenance.source}={second.price}",
            )
        )
    return ValidationReport(tuple(issues))
