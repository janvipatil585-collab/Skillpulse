from contextlib import asynccontextmanager
import os
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.data import router as data_router
from api.health import router as health_router
from app.database import init_db
from app.deployment_config import resolve_cors_origins


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="SkillPulse API", lifespan=lifespan)
environment = os.getenv("ENVIRONMENT", "development")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(resolve_cors_origins(os.getenv("CORS_ORIGINS"), environment)),
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(data_router)