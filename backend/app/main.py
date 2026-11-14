"""FastAPI Modular Monolith Entry Point for Knowledge Handover Platform."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, handovers, health, projects, sources
from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Agentic, evidence-linked, human-approved software project handover and "
            "successor continuation platform."
        ),
        lifespan=lifespan,
    )

    allowed_origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials="*" not in allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # Mount all routers under /api/v1 and /api (to satisfy Round 1 Proposal Section 6.4 exact endpoints)
    for prefix in (settings.API_V1_PREFIX, "/api"):
        app.include_router(health.router, prefix=prefix)
        app.include_router(auth.router, prefix=prefix)
        app.include_router(projects.router, prefix=prefix)
        app.include_router(sources.router, prefix=prefix)
        app.include_router(handovers.router, prefix=prefix)

    return app


app = create_app()
