from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

logger = logging.getLogger(__name__)


async def list_products(products_col: AsyncIOMotorCollection) -> list[dict[str, Any]]:
    items = []
    async for doc in products_col.find({}).sort("_id", 1):
        doc["stock_count"] = len(doc.get("stock", []))
        items.append(doc)
    return items


async def get_product(products_col: AsyncIOMotorCollection, product_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(product_id)
    except Exception:
        return None
    return await products_col.find_one({"_id": oid})


async def claim_one_stock_item(
    products_col: AsyncIOMotorCollection,
    product_id: str,
    max_retry: int = 5,
) -> dict[str, Any] | None:
    """
    Pop one stock item from the product with retry to reduce race issues.
    Returns the claimed stock object (dict) or None when out of stock.
    """

    try:
        oid = ObjectId(product_id)
    except Exception:
        return None

    for _ in range(max_retry):
        product = await products_col.find_one({"_id": oid}, {"stock": 1})
        if not product:
            return None

        stock = product.get("stock", [])
        if not stock:
            return None

        first_item = stock[0]
        res = await products_col.update_one(
            {"_id": oid, "stock.0": first_item},
            {"$pop": {"stock": -1}},
        )
        if res.modified_count == 1:
            if isinstance(first_item, dict):
                return first_item
            return {"content": str(first_item)}

    logger.warning("Could not claim stock after retry", extra={"product_id": product_id})
    return None
