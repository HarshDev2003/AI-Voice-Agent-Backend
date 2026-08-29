from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import close_mongo_client, ensure_indexes
from app.core.health import router as health_router
from app.routers import auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield
    await close_mongo_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

    # CORS: allow the frontend origins configured via CORS_ORIGINS / FRONTEND_URL
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health_router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    return app


app = create_app()
