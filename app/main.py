from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.health import build_health_report
from app.users.router import router as users_router

app = FastAPI(
    title="AI Voice Assistant API",
    version="0.1.0",
    description="Phase 1 - Authentication with Supabase Auth.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/api/health", tags=["health"])
def health_check():
    return build_health_report()
