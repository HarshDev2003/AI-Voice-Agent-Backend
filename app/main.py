from fastapi import FastAPI

from app.core.health import router as health_router

app = FastAPI(title="AI Voice Agent Backend")

app.include_router(health_router)
