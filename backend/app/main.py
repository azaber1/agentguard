"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api.routes import agents, auth, catalog, dashboard, health, runs
from app.core.config import Settings, get_settings
from app.core.security import SecretBox
from app.db.session import session_factory
from app.engine.agents import build_adapter
from app.services.runs import recover_interrupted_runs

log = logging.getLogger("agentguard")

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "AgentGuard"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with app.state.session_factory() as db:
            recovered = recover_interrupted_runs(db)
        if recovered:
            log.warning("Marked %d interrupted run(s) as failed", recovered)
        yield

    docs = settings.environment != "production"
    app = FastAPI(
        title="AgentGuard API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.secret_box = SecretBox(settings.secret_key)
    app.state.session_factory = session_factory()
    app.state.adapter_factory = lambda spec: build_adapter(
        spec, allow_private_urls=settings.allow_private_agent_urls
    )

    @app.middleware("http")
    async def csrf_and_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Browsers cannot attach custom headers to cross-site requests without a CORS
        # preflight, and this API allows no cross-origin requests.
        if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            response: Response = JSONResponse({"detail": "Missing CSRF header."}, status_code=403)
        else:
            response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    for module in (health, auth, agents, catalog, runs, dashboard):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
