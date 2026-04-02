from __future__ import annotations

import hmac

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from web.auth import PageAuth, clear_session, create_session
from web.services.queries import get_stats, get_top_referrers

router = APIRouter()


@router.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login")
async def login_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(request: Request, admin_key: str = Form(...)):
    settings = request.app.state.settings
    templates = request.app.state.templates

    if not hmac.compare_digest(admin_key.strip(), settings.admin_key):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid admin key"},
            status_code=401,
        )

    response = RedirectResponse(url="/dashboard", status_code=303)
    create_session(response, settings)
    return response


@router.get("/tg-login")
async def tg_login(request: Request, token: str = Query(default="")):
    """
    Optional simple Telegram login-like flow.
    Use /tg-login?token=<WEB_ADMIN_KEY> for quick admin access.
    """
    settings = request.app.state.settings
    if not token or not hmac.compare_digest(token, settings.admin_key):
        raise HTTPException(status_code=401, detail="Invalid token")

    response = RedirectResponse(url="/dashboard", status_code=303)
    create_session(response, settings)
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    clear_session(response)
    return response


@router.get("/dashboard")
async def dashboard_page(request: Request, _auth: PageAuth):
    db = request.app.state.db
    templates = request.app.state.templates
    stats = await get_stats(db.collections.users, db.collections.orders)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active": "dashboard",
            "stats": stats,
        },
    )


@router.get("/orders")
async def orders_page(request: Request, _auth: PageAuth):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "active": "orders",
        },
    )


@router.get("/users")
async def users_page(request: Request, _auth: PageAuth):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "active": "users",
        },
    )


@router.get("/analytics")
async def analytics_page(request: Request, _auth: PageAuth):
    db = request.app.state.db
    templates = request.app.state.templates
    top_refs = await get_top_referrers(db.collections.users, limit=20)

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "active": "analytics",
            "top_refs": top_refs,
        },
    )
