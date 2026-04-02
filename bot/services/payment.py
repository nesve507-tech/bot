from __future__ import annotations

import asyncio
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus

from aiogram import Bot
from motor.motor_asyncio import AsyncIOMotorCollection

from bot.config import Settings
from bot.services.delivery import claim_one_stock_item
from bot.services.referral import distribute_commission

logger = logging.getLogger(__name__)

ORDER_ID_PREFIX = "ORD"
ORDER_ID_LEN = 8


def generate_order_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=ORDER_ID_LEN))
    return f"{ORDER_ID_PREFIX}{suffix}"


def build_vietqr_url(settings: Settings, amount: int, order_id: str) -> str:
    add_info = quote_plus(order_id)
    return (
        f"https://img.vietqr.io/image/{settings.vietqr_bank}-{settings.vietqr_account}-compact.png"
        f"?amount={amount}&addInfo={add_info}"
    )


async def create_order(
    orders_col: AsyncIOMotorCollection,
    user_id: int,
    product_id: str,
    amount: int,
) -> dict[str, Any]:
    for _ in range(10):
        order_id = generate_order_id()
        doc = {
            "_id": order_id,
            "user_id": user_id,
            "product_id": product_id,
            "amount": amount,
            "status": "pending",
            "paid": False,
            "created_at": datetime.now(tz=timezone.utc),
            "paid_at": None,
            "delivered_item": None,
            "referral_distributed": False,
        }

        try:
            await orders_col.insert_one(doc)
            return doc
        except Exception:
            continue

    raise RuntimeError("Could not generate unique order id")


async def complete_order(
    bot: Bot,
    users_col: AsyncIOMotorCollection,
    products_col: AsyncIOMotorCollection,
    orders_col: AsyncIOMotorCollection,
    order_id: str,
    source: str = "payment_checker",
) -> bool:
    order = await orders_col.find_one({"_id": order_id})
    if not order:
        return False

    if order.get("status") == "done":
        return True

    locked = await orders_col.update_one(
        {"_id": order_id, "status": "pending", "processing": {"$ne": True}},
        {
            "$set": {
                "processing": True,
                "paid": True,
                "paid_at": datetime.now(tz=timezone.utc),
            }
        },
    )
    if locked.modified_count != 1:
        return False

    stock_item = await claim_one_stock_item(products_col, order["product_id"])
    if not stock_item:
        await orders_col.update_one(
            {"_id": order_id},
            {"$set": {"processing": False, "paid": True}},
        )
        await bot.send_message(
            order["user_id"],
            f"Don {order_id} da thanh toan nhung tam het stock. Admin se xu ly som.",
        )
        logger.warning("Paid order has no stock", extra={"order_id": order_id})
        return False

    update = {
        "$set": {
            "status": "done",
            "paid": True,
            "paid_at": datetime.now(tz=timezone.utc),
            "delivered_item": stock_item,
            "referral_distributed": False,
            "completed_by": source,
            "processing": False,
        }
    }

    res = await orders_col.update_one({"_id": order_id, "status": "pending", "processing": True}, update)
    if res.modified_count != 1:
        return False

    try:
        reward_result = await distribute_commission(users_col, order["user_id"], int(order["amount"]))
        if reward_result:
            await orders_col.update_one({"_id": order_id}, {"$set": {"referral_distributed": True}})
    except Exception:
        logger.exception("Failed to distribute referral", extra={"order_id": order_id})
        reward_result = []

    delivery_text = stock_item.get("content", "")
    note = stock_item.get("note")

    msg_lines = [
        f"Thanh toan thanh cong cho don {order_id}.",
        "Day la thong tin san pham cua ban:",
        f"`{delivery_text}`",
    ]
    if note:
        msg_lines.append(f"Ghi chu: {note}")

    await bot.send_message(order["user_id"], "\n".join(msg_lines), parse_mode="Markdown")

    if reward_result:
        for item in reward_result:
            await bot.send_message(
                item["user_id"],
                f"Ban vua nhan {item['amount']} VND hoa hong F{item['level']}.",
            )

    logger.info("Order completed", extra={"order_id": order_id, "source": source})
    return True


async def find_matching_transactions(settings: Settings) -> list[dict[str, Any]]:
    """
    Placeholder for real bank API integration.
    Return schema example:
    [{"content": "ORDABC123", "amount": 100000, "created_at": datetime(...)}]
    """
    if settings.payment_api_url:
        # TODO: call real payment API here.
        return []

    return []


async def check_and_complete_one_order(
    bot: Bot,
    settings: Settings,
    users_col: AsyncIOMotorCollection,
    products_col: AsyncIOMotorCollection,
    orders_col: AsyncIOMotorCollection,
    order: dict[str, Any],
) -> bool:
    order_id = order["_id"]

    txs = await find_matching_transactions(settings)
    for tx in txs:
        if str(tx.get("content", "")).strip() == order_id and int(tx.get("amount", 0)) == int(order["amount"]):
            return await complete_order(
                bot=bot,
                users_col=users_col,
                products_col=products_col,
                orders_col=orders_col,
                order_id=order_id,
                source="payment_api",
            )

    if settings.payment_mock_enabled:
        created_at: datetime = order.get("created_at") or datetime.now(tz=timezone.utc)
        if datetime.now(tz=timezone.utc) >= created_at + timedelta(seconds=settings.payment_mock_after_sec):
            return await complete_order(
                bot=bot,
                users_col=users_col,
                products_col=products_col,
                orders_col=orders_col,
                order_id=order_id,
                source="mock_payment",
            )

    return False


async def payment_checker_loop(
    bot: Bot,
    settings: Settings,
    users_col: AsyncIOMotorCollection,
    products_col: AsyncIOMotorCollection,
    orders_col: AsyncIOMotorCollection,
    stop_event: asyncio.Event,
) -> None:
    logger.info("Payment checker loop started")
    while not stop_event.is_set():
        try:
            cursor = orders_col.find({"status": "pending", "paid": False}).sort("created_at", 1)
            async for order in cursor:
                await check_and_complete_one_order(
                    bot=bot,
                    settings=settings,
                    users_col=users_col,
                    products_col=products_col,
                    orders_col=orders_col,
                    order=order,
                )
        except Exception:
            logger.exception("Error in payment checker loop")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.payment_check_interval_sec)
        except asyncio.TimeoutError:
            pass

    logger.info("Payment checker loop stopped")
