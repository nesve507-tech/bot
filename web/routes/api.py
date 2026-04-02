from __future__ import annotations

from fastapi import APIRouter, Query, Request

from web.auth import ApiAuth
from web.services.queries import get_orders, get_revenue_series, get_stats, get_top_referrers, get_users

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/stats")
async def stats_api(request: Request, _auth: ApiAuth):
    db = request.app.state.db
    return await get_stats(db.collections.users, db.collections.orders)


@router.get("/orders")
async def orders_api(
    request: Request,
    _auth: ApiAuth,
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    db = request.app.state.db
    return await get_orders(
        db.collections.orders,
        status=status,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/users")
async def users_api(
    request: Request,
    _auth: ApiAuth,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    db = request.app.state.db
    return await get_users(db.collections.users, page=page, page_size=page_size)


@router.get("/revenue")
async def revenue_api(
    request: Request,
    _auth: ApiAuth,
    days: int = Query(default=30, ge=1, le=180),
):
    db = request.app.state.db
    data = await get_revenue_series(db.collections.orders, days=days)
    data["top_referrers"] = await get_top_referrers(db.collections.users, limit=10)
    return data
