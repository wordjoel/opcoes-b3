"""API do B3 Opções Pro. Só leitura e análise: não existe rota de envio de ordens."""

import hmac
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, lab, service
from app.cache import CachingProvider
from core.clock import market_today
from core.config import load_local_env
from core.exceptions import DataInsufficientError
from quant.costs import CostSchedule
from quant.risk import CapitalLimits
from data.normalizer import is_stock_symbol, normalize_symbol
from data.providers.base import DataProvider
from data.providers.brapi import BrapiProvider
from data.providers.composite import SourceChain
from data.providers.cotahist import SHARED_FILES, CotahistProvider, ingest_recent
from db.client import Database, DatabaseError

logger = logging.getLogger("B3.API")


@dataclass(frozen=True)
class Settings:
    password_hash: str | None
    session_secret: str | None
    brapi_configured: bool
    # Só em desenvolvimento, sem HTTPS.
    insecure_cookie: bool = False
    # A Vercel o envia no header Authorization ao chamar o cron.
    cron_secret: str | None = None
    # Atrás do proxy da Vercel, o IP real vem de um header que ela mesma define.
    trust_proxy: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            password_hash=os.environ.get("APP_PASSWORD_HASH"),
            session_secret=os.environ.get("SESSION_SECRET"),
            brapi_configured=bool(os.environ.get("BRAPI_API_KEY")),
            insecure_cookie=os.environ.get("B3_INSECURE_COOKIE") == "1",
            cron_secret=os.environ.get("CRON_SECRET"),
            trust_proxy=bool(os.environ.get("VERCEL")),
        )

    @property
    def login_ready(self) -> bool:
        return bool(self.password_hash and self.session_secret and len(self.session_secret) >= auth.MIN_SECRET_LENGTH)


CACHE_RETENTION = timedelta(days=7)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class RiskSettingsRequest(BaseModel):
    capital_brl: float = Field(gt=0, le=1_000_000_000)
    max_loss_pct: float = Field(gt=0, le=100)


class CostSettingsRequest(BaseModel):
    per_order_brl: float = Field(ge=0, le=10_000)
    fee_pct: float = Field(ge=0, le=5)
    income_tax_pct: float = Field(ge=0, le=100)


class LabStartRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    agent: str
    key: str
    capital_brl: float = Field(gt=0, le=1_000_000_000)
    period_days: int = Field(ge=1, le=365)
    target_pct: float | None = Field(default=None, gt=0, le=10_000)
    stop_pct: float | None = Field(default=None, gt=0, le=100)
    cost_brl: float | None = Field(default=None, ge=0)


class LabBacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    capital_brl: float = Field(gt=0, le=1_000_000_000)
    period_days: int = Field(ge=1, le=60)
    weeks: int = Field(ge=1, le=52)
    target_pct: float | None = Field(default=None, gt=0, le=10_000)
    stop_pct: float | None = Field(default=None, gt=0, le=100)
    cost_brl: float | None = Field(default=None, ge=0)


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


def _valid_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not is_stock_symbol(normalized):
        raise HTTPException(400, f"Código de ativo inválido: {normalized}")
    return normalized


def default_provider(database: Database) -> DataProvider:
    """Sem chave da brapi, o mercado vem dos arquivos oficiais da B3, de graça, para qualquer ativo.
    Com a chave, a brapi vem primeiro e a B3 cobre as falhas. A agenda de eventos só a brapi tem.
    A cotação tenta sempre a brapi: sem chave, ela ainda responde alguns ativos com preço do dia,
    e é esse preço que mede quanto o ativo andou desde a grade."""
    token = os.environ.get("BRAPI_API_KEY")
    brapi = BrapiProvider(token=token)
    official = CotahistProvider(database)
    market = [brapi, official] if token else [official]
    return CachingProvider(SourceChain(market, events=brapi, quotes=[brapi, official]), database)


def create_app(
    settings: Settings | None = None,
    database_factory: Callable[[], Database] | None = None,
    provider_factory: Callable[[Database], DataProvider] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    market_ingest: Callable[[Database, datetime], dict] | None = None,
) -> FastAPI:
    load_local_env()
    config = settings or Settings.from_env()
    make_database = database_factory or Database.from_env
    make_provider = provider_factory or default_provider
    # Com outra fonte injetada não há arquivo da B3 para guardar.
    ingest = market_ingest or (
        (lambda _db, _moment: {"sessions": [], "bars": 0})
        if provider_factory
        else (lambda db, moment: ingest_recent(db, SHARED_FILES, moment))
    )

    app = FastAPI(title="B3 Opções Pro", docs_url=None, redoc_url=None, openapi_url=None)
    router = APIRouter(prefix="/api")

    @app.exception_handler(DataInsufficientError)
    def _insufficient(_: Request, error: DataInsufficientError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"label": error.label, "detail": error.detail, "reasons": error.reasons},
        )

    @app.exception_handler(DatabaseError)
    def _database_error(_: Request, error: DatabaseError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.exception_handler(Exception)
    def _unexpected(_: Request, error: Exception) -> JSONResponse:
        # O detalhe fica no log do servidor: nunca na resposta.
        logger.error("Erro inesperado: %s", type(error).__name__, exc_info=error)
        return JSONResponse(status_code=500, content={"detail": "Erro interno. Nenhum dado foi inventado."})

    @app.middleware("http")
    async def _no_store(request: Request, call_next):
        # Cotação em cache do navegador pareceria atual.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def database() -> Database:
        return make_database()

    def session_ok(request: Request, db: Database) -> bool:
        token = request.cookies.get(auth.COOKIE_NAME)
        if not token or not auth.session_is_valid(token, config.session_secret, now()):
            return False
        return auth.session_is_valid(token, config.session_secret, now(), auth.revoked_before(db))

    def require_session(request: Request, db: Database = Depends(database)) -> None:
        if not config.login_ready:
            raise HTTPException(503, "Login não configurado no servidor")
        if not session_ok(request, db):
            raise HTTPException(401, "Sessão ausente ou vencida")

    def login_origin(request: Request) -> str:
        ip = request.client.host if request.client else "desconhecido"
        if config.trust_proxy:
            ip = request.headers.get("x-vercel-forwarded-for") or request.headers.get("x-real-ip") or ip
        return auth.origin_key(ip.split(",")[0].strip(), config.session_secret)

    def provider(db: Database = Depends(database)) -> DataProvider:
        return make_provider(db)

    def watchlist_symbols(db: Database) -> list[str]:
        return [row[0] for row in db.fetch("SELECT symbol FROM watchlist ORDER BY added_at, symbol")]

    @router.get("/session")
    def session(request: Request, db: Database = Depends(database)) -> dict:
        return {
            "authenticated": config.login_ready and session_ok(request, db),
            "login_ready": config.login_ready,
        }

    @router.post("/login")
    def login(body: LoginRequest, request: Request, response: Response, db: Database = Depends(database)) -> dict:
        if not config.login_ready:
            raise HTTPException(503, "Login não configurado no servidor")
        moment = now()
        origin = login_origin(request)
        if auth.too_many_failures(db, moment, origin):
            raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
        if not auth.verify_password(body.password, config.password_hash):
            auth.record_failure(db, moment, origin)
            raise HTTPException(401, "Senha incorreta")
        auth.clear_failures(db, origin)
        response.set_cookie(
            auth.COOKIE_NAME,
            auth.create_session(config.session_secret, moment),
            max_age=auth.SESSION_SECONDS,
            httponly=True,
            secure=not config.insecure_cookie,
            samesite="strict",
            path="/api",
        )
        return {"authenticated": True}

    @router.post("/logout")
    def logout(request: Request, response: Response, db: Database = Depends(database)) -> dict:
        # Sem sessão válida, ninguém revoga as sessões do proprietário.
        if config.login_ready and session_ok(request, db):
            auth.revoke_sessions(db, now())
        response.delete_cookie(auth.COOKIE_NAME, path="/api")
        return {"authenticated": False}

    protected = [Depends(require_session)]

    def read_capital(db: Database) -> tuple[CapitalLimits | None, str | None]:
        rows = db.fetch("SELECT capital_brl, max_loss_pct, updated_at FROM risk_settings WHERE id = 1")
        return (CapitalLimits(rows[0][0], rows[0][1]), rows[0][2]) if rows else (None, None)

    def capital_view(db: Database) -> dict:
        capital, updated_at = read_capital(db)
        return {
            "capital_brl": capital.capital_brl if capital else None,
            "max_loss_pct": capital.max_loss_pct if capital else None,
            "updated_at": updated_at,
        }

    def read_costs(db: Database) -> tuple[CostSchedule | None, str | None]:
        rows = db.fetch("SELECT per_order_brl, fee_pct, income_tax_pct, updated_at FROM cost_settings WHERE id = 1")
        return (CostSchedule(rows[0][0], rows[0][1], rows[0][2]), rows[0][3]) if rows else (None, None)

    def costs_view(db: Database) -> dict:
        costs, updated_at = read_costs(db)
        return {
            "per_order_brl": costs.per_order_brl if costs else None,
            "fee_pct": costs.fee_pct if costs else None,
            "income_tax_pct": costs.income_tax_pct if costs else None,
            "updated_at": updated_at,
        }

    @router.get("/settings/costs", dependencies=protected)
    def get_cost_settings(db: Database = Depends(database)) -> dict:
        return costs_view(db)

    @router.put("/settings/costs", dependencies=protected)
    def put_cost_settings(body: CostSettingsRequest, db: Database = Depends(database)) -> dict:
        db.run(
            "INSERT INTO cost_settings (id, per_order_brl, fee_pct, income_tax_pct, updated_at) VALUES (1, ?, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET per_order_brl = excluded.per_order_brl, fee_pct = excluded.fee_pct, "
            "income_tax_pct = excluded.income_tax_pct, updated_at = excluded.updated_at",
            (body.per_order_brl, body.fee_pct, body.income_tax_pct, now().isoformat()),
        )
        return costs_view(db)

    @router.get("/settings/risk", dependencies=protected)
    def get_risk_settings(db: Database = Depends(database)) -> dict:
        return capital_view(db)

    @router.put("/settings/risk", dependencies=protected)
    def put_risk_settings(body: RiskSettingsRequest, db: Database = Depends(database)) -> dict:
        db.run(
            "INSERT INTO risk_settings (id, capital_brl, max_loss_pct, updated_at) VALUES (1, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET capital_brl = excluded.capital_brl, "
            "max_loss_pct = excluded.max_loss_pct, updated_at = excluded.updated_at",
            (body.capital_brl, body.max_loss_pct, now().isoformat()),
        )
        return capital_view(db)

    @router.get("/status", dependencies=protected)
    def status() -> dict:
        return {"brapi_token": config.brapi_configured, "order_routing": False}

    @router.get("/watchlist", dependencies=protected)
    def get_watchlist(db: Database = Depends(database)) -> dict:
        return {"symbols": watchlist_symbols(db)}

    @router.post("/watchlist", dependencies=protected)
    def add_watchlist(body: WatchlistRequest, db: Database = Depends(database)) -> dict:
        db.run(
            "INSERT INTO watchlist (symbol, added_at) VALUES (?, ?) ON CONFLICT (symbol) DO NOTHING",
            (_valid_symbol(body.symbol), now().isoformat()),
        )
        return {"symbols": watchlist_symbols(db)}

    @router.delete("/watchlist/{symbol}", dependencies=protected)
    def remove_watchlist(symbol: str, db: Database = Depends(database)) -> dict:
        db.run("DELETE FROM watchlist WHERE symbol = ?", (_valid_symbol(symbol),))
        return {"symbols": watchlist_symbols(db)}

    @router.get("/scanner", dependencies=protected)
    def get_scanner(db: Database = Depends(database), source: DataProvider = Depends(provider)) -> dict:
        return service.scanner(source, watchlist_symbols(db), now())

    @router.get("/cron/scan")
    def cron_scan(
        request: Request, db: Database = Depends(database), source: DataProvider = Depends(provider)
    ) -> dict:
        """Varredura diária: aquece o cache e continua o histórico de IV sem depender do app aberto.

        Pode rodar duas vezes sem efeito: amostra já guardada não é buscada de novo.
        """
        if not config.cron_secret or len(config.cron_secret) < auth.MIN_SECRET_LENGTH:
            raise HTTPException(503, "Cron não configurado no servidor")
        expected = f"Bearer {config.cron_secret}".encode()
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), expected):
            raise HTTPException(401, "Não autorizado")
        moment = now()
        try:
            ingested = ingest(db, moment)
        except DataInsufficientError as error:
            # A varredura ainda aproveita o que já está guardado.
            ingested = {"sessions": [], "bars": 0, "error": error.detail}
        result = service.scanner(source, watchlist_symbols(db), moment)
        monitored = lab.monitor(source, db, moment, budget_seconds=15.0)
        # Só a cópia temporária da fonte: o histórico de vol nunca é apagado.
        limit = (moment - CACHE_RETENTION).isoformat()
        db.run("DELETE FROM provider_cache WHERE fetched_at < ?", (limit,))
        rows = result["rows"]
        return {
            "symbols": len(rows),
            "complete": sum(not row["missing"] for row in rows),
            "iv_samples": sum(row["iv_samples"] for row in rows),
            "scan_complete": result["complete"],
            "b3": ingested,
            "lab": {key: monitored[key] for key in ("active", "marked", "closed", "not_reached")},
        }

    @router.get("/lab/opportunities", dependencies=protected)
    def lab_opportunities(db: Database = Depends(database), source: DataProvider = Depends(provider)) -> dict:
        capital, _ = read_capital(db)
        costs, _ = read_costs(db)
        return lab.discover(source, watchlist_symbols(db), now(), capital, costs=costs)

    @router.post("/lab/strategies", dependencies=protected)
    def lab_start(body: LabStartRequest, db: Database = Depends(database), source: DataProvider = Depends(provider)) -> dict:
        plan = lab.LabPlan(body.capital_brl, body.period_days, body.target_pct, body.stop_pct, body.cost_brl, read_costs(db)[0])
        return lab.start_forward(source, db, _valid_symbol(body.symbol), body.agent, body.key, plan, now())

    @router.get("/lab/strategies", dependencies=protected)
    def lab_list(mode: Literal["FORWARD", "BACKTEST"] | None = None, db: Database = Depends(database)) -> dict:
        return {"strategies": lab.list_strategies(db, mode)}

    @router.get("/lab/strategies/{identity}", dependencies=protected)
    def lab_detail(identity: str, db: Database = Depends(database)) -> dict:
        detail = lab.strategy_detail(db, identity)
        if detail is None:
            raise HTTPException(404, "Estratégia não encontrada")
        return detail

    @router.post("/lab/monitor", dependencies=protected)
    def lab_monitor(db: Database = Depends(database), source: DataProvider = Depends(provider)) -> dict:
        return lab.monitor(source, db, now())

    @router.post("/lab/backtests", dependencies=protected)
    def lab_backtest(body: LabBacktestRequest, db: Database = Depends(database), source: DataProvider = Depends(provider)) -> dict:
        plan = lab.LabPlan(body.capital_brl, body.period_days, body.target_pct, body.stop_pct, body.cost_brl, read_costs(db)[0])
        return lab.run_backtest(source, db, _valid_symbol(body.symbol), plan, body.weeks, now())

    @router.get("/lab/ranking", dependencies=protected)
    def lab_ranking(mode: Literal["FORWARD", "BACKTEST"], db: Database = Depends(database)) -> dict:
        return lab.ranking(db, mode)

    @router.get("/assets/{symbol}", dependencies=protected)
    def get_asset(symbol: str, source: DataProvider = Depends(provider)) -> dict:
        return service.asset_overview(source, _valid_symbol(symbol), now())

    @router.get("/assets/{symbol}/expirations", dependencies=protected)
    def get_expirations(symbol: str, source: DataProvider = Depends(provider)) -> dict:
        today = market_today(now())
        days = [day for day in source.get_expirations(_valid_symbol(symbol)) if day >= today]
        return {"expirations": [day.isoformat() for day in days]}

    @router.get("/assets/{symbol}/chain", dependencies=protected)
    def get_chain(symbol: str, expiry: date, source: DataProvider = Depends(provider)) -> dict:
        return service.chain_view(source, _valid_symbol(symbol), expiry, now())

    @router.get("/assets/{symbol}/strategies", dependencies=protected)
    def get_strategies(
        symbol: str,
        expiry: date,
        profile: Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"] | None = None,
        source: DataProvider = Depends(provider),
        db: Database = Depends(database),
    ) -> dict:
        capital, _ = read_capital(db)
        costs, _ = read_costs(db)
        return service.strategies_view(source, _valid_symbol(symbol), expiry, now(), profile=profile, capital=capital, costs=costs)

    app.include_router(router)
    return app


app = create_app()
