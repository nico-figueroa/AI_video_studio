from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from database import Base, STORAGE_DIR, engine
from models import models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AI Video Studio API",
    description="Local-first story planning, transparent estimates, and slideshow video export.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Video Studio", "docs": "/docs", "status": "ok"}
