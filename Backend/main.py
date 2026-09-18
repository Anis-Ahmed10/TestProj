"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.api.v1.router import api_router
from app.components.authorizer.seed import seed_rbac_defaults
from app.core.config import get_settings
from app.core.connection import postgres_session
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging, logger
from app.middleware.body_size import BodySizeLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.common import HealthData, SuccessResponse
from app.utils.jwt import _get_jwks

settings = get_settings()
configure_logging(settings)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown hooks."""
    logger.info("Starting application")
    with postgres_session() as db:
        seed_rbac_defaults(db)
    _get_jwks()
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-powered QA/Test Engineering backend",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

handler = Mangum(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BodySizeLimitMiddleware, max_body_size=settings.max_input_bytes)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=SuccessResponse[HealthData], tags=["Health"])
async def health_check() -> SuccessResponse[HealthData]:
    """Return basic service health."""
    return SuccessResponse(
        message="Service is healthy",
        data=HealthData(status="ok", service=settings.app_name),
    )
