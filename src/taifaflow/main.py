from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from taifaflow.api.routes.dashboard import router as dashboard_router
from taifaflow.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(dashboard_router)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app


app = create_app()
