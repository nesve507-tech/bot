from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.config import get_settings
from web.db import WebDatabase
from web.routes.api import router as api_router
from web.routes.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = WebDatabase(settings)
    await db.ping()

    app.state.settings = settings
    app.state.db = db
    app.state.templates = Jinja2Templates(directory="web/templates")
    yield
    db.close()


app = FastAPI(title="Telegram Bot Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.include_router(pages_router)
app.include_router(api_router)
