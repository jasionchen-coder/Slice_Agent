from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import clips, tasks
from app.core.config import settings
from app.db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.storage_root), name="media")

    app.include_router(tasks.router, prefix="/api")
    app.include_router(clips.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

