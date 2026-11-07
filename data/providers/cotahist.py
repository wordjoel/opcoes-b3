"""Fonte oficial e gratuita: arquivos COTAHIST da B3, um por pregão, e Selic do Banco Central.

Regras conferidas com os arquivos reais (28 e 30/10/2026):
- O arquivo do dia é publicado por volta das 21h. Antes disso, ou em feriado, a resposta é 404.
- Em 28/10/2026, as 217 séries negociadas de PETR4 tiveram fechamento, strike e vencimento
  idênticos aos da brapi.
- A opção traz o ISIN do ativo-objeto, que é o que liga a série à ação (ON e PN têm a mesma raiz).
- O nome da série diz o estilo: raiz + "E" é europeia; só a raiz é americana. VALE e WEGE terminam
  em "E", então a comparação é com a raiz, não com a última letra.
- Só aparecem séries negociadas no pregão. Não há contratos em aberto: o campo fica nulo, nunca zero.
- O histórico não é ajustado por proventos.
"""

import io
import threading
import time
import zipfile
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from statistics import median

import httpx

from core.clock import market_today
from core.exceptions import DataInsufficientError
from core.types import (
    CorporateEvent,
    ExerciseStyle,
    MarketSnapshot,
    OptionChain,
    OptionKind,
    OptionQuote,
    PriceBar,
    Provenance,
    SourceKind,
)
from data.normalizer import normalize_symbol
from data.providers.b3_eventos import B3CorporateActions, adjust_bars
from data.providers.base import AtmIvSample, DataProvider
from db.client import Database
from quant.greeks import option_greeks
from quant.volatility import implied_volatility

SOURCE = "B3 COTAHIST"
_FILE_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_{stamp}.ZIP"
_SELIC_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados"
_HEADERS = {"User-Agent": "Mozilla/5.0 (B3 Opcoes Pro)"}
_BRT = timezone(timedelta(hours=-3))
_SESSION_CLOSE_HOUR = 18
_TIMEOUT_SECONDS = 25.0
_MEMORY_SESSIONS = 8
# O arquivo de hoje pode sair a qualquer momento: a ausência só vale por um tempo curto.
_ABSENT_TTL_SECONDS = 15 * 60
_LOOKBACK_DAYS = 10
_MIN_DAYS_TO_EXPIRY = 20
_ATM_BAND = 0.05
_MIN_ATM_VALUES = 2
_LOOKBACK_TO_DAYS = {"1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731}
_INSERT_CHUNK = 200
_INGEST_MAX_DAYS = 14


@dataclass(frozen=True)
class StockRow:
    symbol: str
    name: str
    isin: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: int


@dataclass(frozen=True)
class OptionRow:
    symbol: str
    isin: str
    kind: OptionKind
    style: ExerciseStyle | None
    strike: float
    expiry: date
    close: float
    bid: float
    ask: float
    volume: int
    trades: int

    @property
    def weekly(self) -> bool:
        return self.symbol[-2:-1] == "W"


@dataclass
class Session:
    day: date
    stocks: dict[str, StockRow] = field(default_factory=dict)
    options: dict[str, list[OptionRow]] = field(default_factory=dict)

    def add(self, row: StockRow | OptionRow) -> None:
        if isinstance(row, StockRow):
            self.stocks[row.symbol] = row
        else:
            self.options.setdefault(row.isin, []).append(row)


def _style(symbol: str, name: str) -> ExerciseStyle | None:
    root, token = symbol[:4], (name.split() or [""])[0]
    if token == root + "E":
        return ExerciseStyle.EUROPEAN
    if token == root:
        return ExerciseStyle.AMERICAN
    return None


def parse_line(line: str) -> tuple[date, StockRow | OptionRow] | None:
    """Layout oficial do COTAHIST. Fora de ação em lote-padrão e de opção: None."""
    market = line[24:27]
    if line[:2] != "01" or market not in ("010", "070", "080"):
        return None
    if market == "010" and line[10:12] != "02":
        return None
    factor = int(line[210:217]) or 1

    def price(start: int, end: int) -> float:
        return int(line[start:end]) / 100 / factor

    day = date(int(line[2:6]), int(line[6:8]), int(line[8:10]))
    symbol, name, isin = line[12:24].strip(), line[27:39].strip(), line[230:242]
    volume, trades = int(line[152:170]), int(line[147:152])
    if market == "010":
        return day, StockRow(
            symbol, name, isin, price(56, 69), price(69, 82), price(82, 95), price(108, 121), volume, trades
        )
    return day, OptionRow(
        symbol=symbol,
        isin=isin,
        kind=OptionKind.CALL if market == "070" else OptionKind.PUT,
        style=_style(symbol, name),
        strike=int(line[188:201]) / 100,
        expiry=date(int(line[202:206]), int(line[206:208]), int(line[208:210])),
        close=price(108, 121),
        bid=price(121, 134),
        ask=price(134, 147),
        volume=volume,
        trades=trades,
    )


def parse_daily_file(content: bytes, day: date) -> Session:
    """Confere data e rodapé: um arquivo de outro dia ou cortado não pode virar dado do pregão."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            lines = archive.read(archive.namelist()[0]).decode("latin-1").splitlines()
    except (zipfile.BadZipFile, IndexError, KeyError) as error:
        raise DataInsufficientError(f"arquivo da B3 de {day} ilegível ({type(error).__name__})") from None
    if len(lines) < 2 or not lines[0].startswith("00COTAHIST") or not lines[-1].startswith("99COTAHIST"):
        raise DataInsufficientError(f"arquivo da B3 de {day} incompleto")
    stamp = lines[0][23:31]
    if stamp != day.strftime("%Y%m%d"):
        raise DataInsufficientError(f"arquivo da B3 de {day} traz outra data: {stamp}")
    session = Session(day)
    for line in lines[1:-1]:
        parsed = parse_line(line)
        if parsed:
            session.add(parsed[1])
    return session


class SelicRates:
    """Meta Selic (SGS 432), em decimal: a mesma taxa que a brapi informa em cada grade."""

    def __init__(self, get: Callable[..., httpx.Response] = httpx.get) -> None:
        self._get = get
        self._known: dict[date, float] = {}

    def load_range(self, start: date, end: date) -> None:
        params = {"formato": "json", "dataInicial": start.strftime("%d/%m/%Y"), "dataFinal": end.strftime("%d/%m/%Y")}
        try:
            response = self._get(_SELIC_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            for item in response.json():
                self._known[datetime.strptime(item["data"], "%d/%m/%Y").date()] = float(item["valor"]) / 100
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise DataInsufficientError(f"Banco Central sem Selic ({type(error).__name__})") from None

    def rate_on(self, day: date) -> float:
        """Sem taxa não há vol nem prazo confiáveis: levanta erro em vez de usar um padrão."""
        if day not in self._known:
            self.load_range(day, day)
        if day not in self._known:
            raise DataInsufficientError(f"Banco Central sem Selic para {day}")
        return self._known[day]


class CotahistFiles:
    """Baixa e guarda em memória os pregões. 404 é "sem arquivo"; outra falha é erro de acesso."""

    def __init__(self, get: Callable[..., httpx.Response] = httpx.get) -> None:
        self._get = get
        self._lock = threading.Lock()
        self._sessions: OrderedDict[date, Session] = OrderedDict()
        self._absent: dict[date, float] = {}

    def session(self, day: date) -> Session | None:
        with self._lock:
            if day in self._sessions:
                self._sessions.move_to_end(day)
                return self._sessions[day]
            noted = self._absent.get(day)
            if noted is not None and time.monotonic() - noted < _ABSENT_TTL_SECONDS:
                return None
            url = _FILE_URL.format(stamp=f"D{day.strftime('%d%m%Y')}")
            try:
                response = self._get(url, headers=_HEADERS, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
            except httpx.HTTPError as error:
                raise DataInsufficientError(f"B3 indisponível ({type(error).__name__})") from None
            if response.status_code == 404:
                self._absent[day] = time.monotonic()
                return None
            if response.status_code != 200:
                raise DataInsufficientError(f"B3 respondeu {response.status_code}")
            session = parse_daily_file(response.content, day)
            self._sessions[day] = session
            while len(self._sessions) > _MEMORY_SESSIONS:
                self._sessions.popitem(last=False)
            return session

    def _walk_back(self, first: date, lookback_days: int) -> Session | None:
        for back in range(lookback_days + 1):
            day = first - timedelta(days=back)
            if day.weekday() < 5:
                session = self.session(day)
                if session:
                    return session
        return None

    def latest(self, today: date, lookback_days: int = _LOOKBACK_DAYS) -> Session:
        session = self._walk_back(today, lookback_days)
        if session is None:
            raise DataInsufficientError(f"B3 sem arquivo de pregão nos {lookback_days} dias até {today}")
        return session

    def previous(self, day: date) -> Session | None:
        return self._walk_back(day - timedelta(days=1), _LOOKBACK_DAYS)


def atm_iv_sample(session: Session, symbol: str, rate: float) -> AtmIvSample | None:
    """Mediana das vols perto do ativo, no vencimento mensal mais próximo a pelo menos 20 dias."""
    stock = session.stocks.get(symbol)
    if not stock or not stock.close:
        return None
    by_expiry: dict[date, list[OptionRow]] = {}
    for row in session.options.get(stock.isin, []):
        days = (row.expiry - session.day).days
        if days >= _MIN_DAYS_TO_EXPIRY and not row.weekly and row.close and abs(row.strike / stock.close - 1) <= _ATM_BAND:
            by_expiry.setdefault(row.expiry, []).append(row)
    for expiry in sorted(by_expiry):
        t = (expiry - session.day).days / 365
        values = [
            iv
            for row in by_expiry[expiry]
            if (iv := implied_volatility(row.kind, row.close, stock.close, row.strike, t, rate))
        ]
        if len(values) >= _MIN_ATM_VALUES:
            return AtmIvSample(session.day, median(values), expiry)
    return None


def _insert_rows(database: Database, head: str, columns: int, rows: list[tuple]) -> None:
    """Várias linhas por comando: uma por vez levaria minutos pela rede."""
    placeholder = "(" + ", ".join("?" * columns) + ")"
    for start in range(0, len(rows), _INSERT_CHUNK):
        chunk = rows[start : start + _INSERT_CHUNK]
        values = ", ".join([placeholder] * len(chunk))
        database.run(f"{head} VALUES {values} ON CONFLICT DO NOTHING", [value for row in chunk for value in row])


def store_bars(database: Database, day: date, stocks: Iterable[StockRow], now: datetime) -> int:
    rows = [
        (s.symbol, day.isoformat(), s.open, s.high, s.low, s.close, s.volume, s.trades, now.isoformat())
        for s in stocks
        if s.open and s.high and s.low and s.close
    ]
    head = "INSERT INTO b3_daily_bars (symbol, day, open, high, low, close, volume, trades, fetched_at)"
    _insert_rows(database, head, 9, rows)
    return len(rows)


def store_iv_samples(database: Database, samples: Iterable[tuple[str, AtmIvSample]], now: datetime) -> int:
    """Não sobrescreve: a amostra que já existe, inclusive a vinda da brapi, fica como está."""
    rows = [(symbol, s.day.isoformat(), s.iv, s.expiry.isoformat(), now.isoformat()) for symbol, s in samples]
    _insert_rows(database, "INSERT INTO iv_history (symbol, day, iv, expiry, fetched_at)", 5, rows)
    return len(rows)


def optioned_stocks(session: Session) -> list[StockRow]:
    return [stock for stock in session.stocks.values() if stock.isin in session.options]


def ingest_recent(database: Database, files: CotahistFiles, now: datetime) -> dict:
    """Guarda os pregões depois do último salvo: costuma ser um arquivo só, e cobre um cron que falhou.
    Pode repetir sem efeito. O limite impede estourar o tempo da função depois de uma longa parada."""
    today = market_today(now)
    stored = database.fetch("SELECT max(day) FROM b3_daily_bars")[0][0]
    first = date.fromisoformat(stored) + timedelta(days=1) if stored else today - timedelta(days=_LOOKBACK_DAYS)
    first = max(first, today - timedelta(days=_INGEST_MAX_DAYS))
    sessions, bars = [], 0
    for offset in range((today - first).days + 1):
        day = first + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        session = files.session(day)
        if session:
            bars += store_bars(database, day, optioned_stocks(session), now)
            sessions.append(day.isoformat())
    return {"sessions": sessions, "bars": bars}


# Compartilhados no processo: 8 ativos não podem baixar 8 vezes o mesmo arquivo.
SHARED_FILES = CotahistFiles()
SHARED_RATES = SelicRates()


class CotahistProvider(DataProvider):
    def __init__(
        self,
        database: Database,
        files: CotahistFiles | None = None,
        rates: SelicRates | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        actions: B3CorporateActions | None = None,
    ) -> None:
        """`actions`: eventos corporativos para ajustar o histórico. None = histórico sem ajuste."""
        self._database = database
        self._actions = actions
        self._files = files or SHARED_FILES
        self._rates = rates or SHARED_RATES
        self._now = now

    def _provenance(self, day: date) -> Provenance:
        close = datetime(day.year, day.month, day.day, _SESSION_CLOSE_HOUR, tzinfo=_BRT)
        return Provenance(source=SOURCE, kind=SourceKind.EOD, collected_at=self._now(), market_time=close)

    def _latest(self) -> Session:
        return self._files.latest(market_today(self._now()))

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        symbol = normalize_symbol(symbol)
        session = self._latest()
        stock = session.stocks.get(symbol)
        if not stock or not stock.close:
            raise DataInsufficientError(f"B3 sem negócios de {symbol} em {session.day}")
        previous = self._files.previous(session.day)
        before = previous.stocks.get(symbol) if previous else None
        return MarketSnapshot(
            symbol=symbol,
            price=stock.close,
            volume=stock.volume,
            name=stock.name,
            change_percent=(stock.close / before.close - 1) * 100 if before and before.close else None,
            provenance=self._provenance(session.day),
        )

    def get_expirations(self, underlying: str) -> list[date]:
        symbol = normalize_symbol(underlying)
        session = self._latest()
        stock = session.stocks.get(symbol)
        rows = session.options.get(stock.isin, []) if stock else []
        days = sorted({row.expiry for row in rows if row.expiry > session.day})
        if not days:
            raise DataInsufficientError(f"B3 sem opções negociadas de {symbol} em {session.day}")
        return days

    def _chain(self, session: Session, symbol: str, expiry: date) -> OptionChain | None:
        stock = session.stocks.get(symbol)
        rows = [row for row in session.options.get(stock.isin, []) if row.expiry == expiry] if stock else []
        days = (expiry - session.day).days
        if not stock or not stock.close or not rows or days <= 0:
            return None
        # Mesma convenção da brapi, conferida nas grades guardadas: dias corridos sobre 365.
        t, rate = days / 365, self._rates.rate_on(session.day)
        provenance = self._provenance(session.day)
        quotes = []
        for row in rows:
            iv = implied_volatility(row.kind, row.close, stock.close, row.strike, t, rate) if row.close else None
            quotes.append(
                OptionQuote(
                    symbol=row.symbol,
                    underlying=symbol,
                    kind=row.kind,
                    strike=row.strike,
                    expiry=row.expiry,
                    style=row.style,
                    bid=row.bid,
                    ask=row.ask,
                    volume=row.volume,
                    trades=row.trades,
                    close=row.close,
                    last_trade_date=session.day,
                    iv=iv,
                    delta=option_greeks(row.kind, stock.close, row.strike, t, rate, iv).delta if iv else None,
                    provenance=provenance,
                )
            )
        return OptionChain(
            underlying=MarketSnapshot(symbol=symbol, price=stock.close, provenance=provenance),
            quotes=quotes,
            market_date=session.day,
            risk_free_rate=rate,
            time_to_expiry_years=t,
        )

    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain:
        symbol = normalize_symbol(underlying)
        session = self._latest()
        chain = self._chain(session, symbol, expiry)
        if chain is None:
            raise DataInsufficientError(f"B3 sem grade de {symbol} para {expiry} em {session.day}")
        return chain

    def get_option_chain_on(self, underlying: str, expiry: date, day: date) -> OptionChain | None:
        session = self._files.session(day)
        return self._chain(session, normalize_symbol(underlying), expiry) if session else None

    def get_atm_iv_on(self, underlying: str, day: date) -> AtmIvSample | None:
        session = self._files.session(day)
        if session is None:
            # Hoje, antes das 21h, a ausência é só atraso: não pode ser guardada como dia sem dado.
            if day >= market_today(self._now()):
                raise DataInsufficientError(f"arquivo da B3 de {day} ainda não publicado")
            return None
        return atm_iv_sample(session, normalize_symbol(underlying), self._rates.rate_on(day))

    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]:
        symbol = normalize_symbol(symbol)
        days = _LOOKBACK_TO_DAYS.get(lookback, _LOOKBACK_TO_DAYS["1y"])
        start = market_today(self._now()) - timedelta(days=days)
        rows = self._database.fetch(
            "SELECT day, open, high, low, close, volume FROM b3_daily_bars WHERE symbol = ? AND day >= ? ORDER BY day",
            (symbol, start.isoformat()),
        )
        points = {date.fromisoformat(row[0]): row[1:] for row in rows}
        # O cron guarda o pregão à noite; até lá, o mais recente vem do próprio arquivo.
        session = self._latest()
        stock = session.stocks.get(symbol)
        if stock and stock.open and stock.high and stock.low and stock.close and session.day not in points:
            points[session.day] = (stock.open, stock.high, stock.low, stock.close, stock.volume)
        if not points:
            raise DataInsufficientError(f"histórico de {symbol} ainda não carregado da B3")
        bars = [
            PriceBar(
                symbol=symbol,
                day=day,
                open=point[0],
                high=point[1],
                low=point[2],
                close=point[3],
                volume=point[4],
                adjusted=False,
                provenance=self._provenance(day),
            )
            for day, point in sorted(points.items())
        ]
        return self._adjusted(bars, stock.isin if stock else None, symbol)

    def _adjusted(self, bars: list[PriceBar], isin: str | None, symbol: str) -> list[PriceBar]:
        """Sem eventos ou sem ISIN, devolve sem ajuste, marcado como tal: a tela avisa."""
        if self._actions is None or not isin:
            return bars
        try:
            cash, shares = self._actions.events(symbol[:4])
        except DataInsufficientError:
            return bars
        if not any(event.isin == isin for event in [*cash, *shares]):
            # Nenhum evento deste ISIN (comum em units): não dá para afirmar que não houve provento.
            return bars
        return adjust_bars(bars, isin, cash, shares)

    def get_upcoming_events(self, symbol: str, today: date) -> list[CorporateEvent]:
        raise DataInsufficientError("a B3 não publica a agenda de eventos neste arquivo")
