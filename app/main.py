"""API do B3 Opções Pro. Só leitura e análise: não existe rota de envio de ordens."""

import hmac
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, service
from app.cache import CachingProvider
from core.config import load_local_env
from core.exceptions import DataInsufficientError
from data.normalizer import is_stock_symbol, normalize_symbol
from data.providers.base import DataProvider
from data.providers.brapi import BrapiProvider
from db.client import Database, DatabaseError


@dataclass(frozen=True)
class Settings:
    password_hash: str | None
    session_secret: str | None
    brapi_configured: bool
    # Só em desenvolvimento, sem HTTPS.
    insecure_cookie: bool = False
    # A Vercel o envia no header Authorization ao chamar o cron.
    cron_secret: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            password_hash=os.environ.get("APP_PASSWORD_HASH"),
            session_secret=os.environ.get("SESSION_SECRET"),
            brapi_configured=bool(os.environ.get("BRAPI_API_KEY")),
            insecure_cookie=os.environ.get("B3_INSECURE_COOKIE") == "1",
            cron_secret=os.environ.get("CRON_SECRET"),
        )

    @property
    def login_ready(self) -> bool:
        return bool(self.password_hash and self.session_secret and len(self.session_secret) >= auth.MIN_SECRET_LENGTH)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


def _valid_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not is_stock_symbol(normalized):
        raise HTTPException(400, f"Código de ativo inválido: {normalized}")
    return normalized


def create_app(
    settings: Settings | None = None,
    database_factory: Callable[[], Database] | None = None,
    provider_factory: Callable[[Database], DataProvider] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> FastAPI:
    load_local_env()
    config = settings or Settings.from_env()
    make_database = database_factory or Database.from_env
    make_provider = provider_factory or (
        lambda database: CachingProvider(BrapiProvider(token=os.environ.get("BRAPI_API_KEY")), database)
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

    @app.middleware("http")
    async def _no_store(request: Request, call_next):
        # Cotação em cache do navegador pareceria atual.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def database() -> Database:
        return make_database()

    def require_session(request: Request) -> None:
        if not config.login_ready:
            raise HTTPException(503, "Login não configurado no servidor")
        if not auth.session_is_valid(request.cookies.get(auth.COOKIE_NAME), config.session_secret, now()):
            raise HTTPException(401, "Sessão ausente ou vencida")

    def provider(db: Database = Depends(database)) -> DataProvider:
        return make_provider(db)

    def watchlist_symbols(db: Database) -> list[str]:
        return [row[0] for row in db.fetch("SELECT symbol FROM watchlist ORDER BY added_at, symbol")]

    @router.get("/session")
    def session(request: Request) -> dict:
        return {
            "authenticated": config.login_ready
            and auth.session_is_valid(request.cookies.get(auth.COOKIE_NAME), config.session_secret, now()),
            "login_ready": config.login_ready,
        }

    @router.post("/login")
    def login(body: LoginRequest, response: Response, db: Database = Depends(database)) -> dict:
        if not config.login_ready:
            raise HTTPException(503, "Login não configurado no servidor")
        moment = now()
        if auth.too_many_failures(db, moment):
            raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
        if not auth.verify_password(body.password, config.password_hash):
            auth.record_failure(db, moment)
            raise HTTPException(401, "Senha incorreta")
        auth.clear_failures(db)
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
    def logout(response: Response) -> dict:
        response.delete_cookie(auth.COOKIE_NAME, path="/api")
        return {"authenticated": False}

    protected = [Depends(require_session)]

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
        rows = service.scanner(source, watchlist_symbols(db), now())["rows"]
        return {
            "symbols": len(rows),
            "complete": sum(not row["missing"] for row in rows),
            "iv_samples": sum(row["iv_samples"] for row in rows),
        }

    @router.get("/assets/{symbol}", dependencies=protected)
    def get_asset(symbol: str, source: DataProvider = Depends(provider)) -> dict:
        return service.asset_overview(source, _valid_symbol(symbol), now())

    @router.get("/assets/{symbol}/expirations", dependencies=protected)
    def get_expirations(symbol: str, source: DataProvider = Depends(provider)) -> dict:
        today = now().date()
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
    ) -> dict:
        return service.strategies_view(source, _valid_symbol(symbol), expiry, now(), profile=profile)

    app.include_router(router)
    return app


app = create_app()
