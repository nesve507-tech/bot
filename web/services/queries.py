from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection


def _utc_day_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    dt = now or datetime.now(tz=timezone.utc)
    start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


async def get_stats(users_col: AsyncIOMotorCollection, orders_col: AsyncIOMotorCollection) -> dict[str, int]:
    today_start, today_end = _utc_day_range()

    total_users = await users_col.count_documents({})
    total_orders = await orders_col.count_documents({})
    orders_today = await orders_col.count_documents({"created_at": {"$gte": today_start, "$lt": today_end}})

    rev_pipeline = [
        {"$match": {"status": "done"}},
        {"$group": {"_id": None, "value": {"$sum": "$amount"}}},
    ]
    rev_today_pipeline = [
        {
            "$match": {
                "status": "done",
                "paid_at": {"$gte": today_start, "$lt": today_end},
            }
        },
        {"$group": {"_id": None, "value": {"$sum": "$amount"}}},
    ]

    total_revenue_docs = [doc async for doc in orders_col.aggregate(rev_pipeline)]
    revenue_today_docs = [doc async for doc in orders_col.aggregate(rev_today_pipeline)]

    return {
        "total_users": int(total_users),
        "total_orders": int(total_orders),
        "orders_today": int(orders_today),
        "total_revenue": int(total_revenue_docs[0]["value"]) if total_revenue_docs else 0,
        "revenue_today": int(revenue_today_docs[0]["value"]) if revenue_today_docs else 0,
    }


async def get_revenue_series(orders_col: AsyncIOMotorCollection, days: int = 30) -> dict[str, list[Any]]:
    days = max(1, min(days, 180))
    start = datetime.now(tz=timezone.utc) - timedelta(days=days - 1)
    start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)

    pipeline = [
        {"$match": {"created_at": {"$gte": start}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "orders": {"$sum": 1},
                "revenue": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "done"]}, "$amount", 0]
                    }
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]

    rows = [doc async for doc in orders_col.aggregate(pipeline)]
    by_day = {r["_id"]: r for r in rows}

    labels: list[str] = []
    orders: list[int] = []
    revenue: list[int] = []

    cursor = start
    for _ in range(days):
        key = cursor.strftime("%Y-%m-%d")
        labels.append(key)
        row = by_day.get(key)
        orders.append(int(row["orders"]) if row else 0)
        revenue.append(int(row["revenue"]) if row else 0)
        cursor += timedelta(days=1)

    return {"labels": labels, "orders": orders, "revenue": revenue}


async def get_orders(
    orders_col: AsyncIOMotorCollection,
    *,
    status: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    filt: dict[str, Any] = {}
    if status in {"pending", "done"}:
        filt["status"] = status

    if q:
        q = q.strip()
        search_or: list[dict[str, Any]] = [{"_id": {"$regex": q, "$options": "i"}}]
        if q.isdigit():
            search_or.append({"user_id": int(q)})
        filt["$or"] = search_or

    total = await orders_col.count_documents(filt)
    skip = (page - 1) * page_size

    cursor = orders_col.find(filt).sort("created_at", -1).skip(skip).limit(page_size)
    items = []
    async for doc in cursor:
        items.append(
            {
                "order_id": doc.get("_id"),
                "user_id": doc.get("user_id"),
                "amount": int(doc.get("amount", 0)),
                "status": doc.get("status", "pending"),
                "paid": bool(doc.get("paid", False)),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "total_pages": (int(total) + page_size - 1) // page_size,
    }


async def get_users(users_col: AsyncIOMotorCollection, *, page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    total = await users_col.count_documents({})
    skip = (page - 1) * page_size

    pipeline = [
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": page_size},
        {
            "$lookup": {
                "from": "users",
                "let": {"uid": "$user_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$ref_by", "$$uid"]}}},
                    {"$count": "count"},
                ],
                "as": "f1_count_docs",
            }
        },
    ]

    rows = [row async for row in users_col.aggregate(pipeline)]
    items = []
    for row in rows:
        f1_docs = row.get("f1_count_docs", [])
        f1_count = int(f1_docs[0]["count"]) if f1_docs else 0
        items.append(
            {
                "user_id": row.get("user_id"),
                "balance": int(row.get("balance", 0)),
                "ref_by": row.get("ref_by"),
                "f1_count": f1_count,
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "total_pages": (int(total) + page_size - 1) // page_size,
    }


async def get_top_referrers(users_col: AsyncIOMotorCollection, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    pipeline = [
        {"$match": {"ref_by": {"$type": "int"}}},
        {"$group": {"_id": "$ref_by", "f1_count": {"$sum": 1}}},
        {"$sort": {"f1_count": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "user_docs",
            }
        },
    ]

    rows = [row async for row in users_col.aggregate(pipeline)]
    result: list[dict[str, Any]] = []
    for row in rows:
        user_docs = row.get("user_docs", [])
        balance = int(user_docs[0].get("balance", 0)) if user_docs else 0
        result.append(
            {
                "user_id": row.get("_id"),
                "f1_count": int(row.get("f1_count", 0)),
                "balance": balance,
            }
        )
    return result
