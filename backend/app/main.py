"""
LifeTrack FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.database import get_engine
from app.schemas.problem import AIProblemDetail, problem_response

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Run Alembic migrations on startup so the schema is always up-to-date.
    This removes the need to manually run `alembic upgrade head`.

    In production, replace with a CI/CD migration step so startup is fast
    and migrations are auditable.
    """
    from alembic.config import Config
    from alembic import command
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def _run_migrations() -> None:
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, _run_migrations)

    yield

    await get_engine().dispose()


app = FastAPI(
    title="LifeTrack API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)


@app.exception_handler(AIProblemDetail)
async def ai_problem_handler(request: Request, exc: AIProblemDetail) -> JSONResponse:
    return problem_response(exc, request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "version": "0.1.0"}