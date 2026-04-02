from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import Database

router = Router(name="payment")


async def _notify_admins_for_order(
    message: Message | CallbackQuery,
    db: Database,
    settings: Settings,
    order: dict,
) -> None:
    product_name = "Unknown"
    product = await db.collections.products.find_one({"_id": order.get("product_id")}, {"name": 1})
    if product:
        product_name = product.get("name", "Unknown")

    text = "\n".join(
        [
            "Yeu cau xac nhan thanh toan moi:",
            f"- Order: {order['_id']}",
            f"- User: {order['user_id']}",
            f"- Product: {product_name}",
            f"- Amount: {order['amount']} VND",
            f"- Approve: /approve {order['_id']}",
        ]
    )

    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, text)
        except Exception:
            # Skip failed admin destinations to keep flow resilient.
            continue


async def _submit_payment_request(
    *,
    actor_user_id: int,
    order_id: str,
    db: Database,
    settings: Settings,
    event: Message | CallbackQuery,
) -> tuple[bool, str]:
    order = await db.collections.orders.find_one({"_id": order_id, "user_id": actor_user_id})
    if not order:
        return False, "Khong tim thay don cua ban."

    if order.get("status") == "done":
        return False, "Don nay da hoan thanh."

    # Idempotent flag to avoid duplicate admin spam for the same pending order.
    updated = await db.collections.orders.update_one(
        {"_id": order_id, "status": "pending", "payment_requested_at": {"$exists": False}},
        {"$set": {"payment_requested_at": datetime.now(tz=timezone.utc)}},
    )

    if updated.modified_count == 0:
        return False, "Ban da gui yeu cau truoc do. Vui long doi admin duyet."

    await _notify_admins_for_order(event, db, settings, order)
    return True, "Da gui yeu cau xac nhan thanh toan cho admin."


@router.callback_query(F.data.startswith("paid_"))
async def i_have_paid_callback(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    order_id = callback.data.replace("paid_", "", 1)
    ok, msg = await _submit_payment_request(
        actor_user_id=callback.from_user.id,
        order_id=order_id,
        db=db,
        settings=settings,
        event=callback,
    )
    await callback.answer(msg, show_alert=not ok)


@router.message(Command("paid"))
async def paid_cmd(message: Message, db: Database, settings: Settings) -> None:
    chunks = message.text.split(maxsplit=1)
    if len(chunks) != 2:
        await message.answer("Dung: /paid ORDXXXX")
        return

    order_id = chunks[1].strip()
    ok, msg = await _submit_payment_request(
        actor_user_id=message.from_user.id,
        order_id=order_id,
        db=db,
        settings=settings,
        event=message,
    )
    await message.answer(msg)


@router.message(Command("order"))
async def order_detail_cmd(message: Message, db: Database) -> None:
    chunks = message.text.split(maxsplit=1)
    if len(chunks) != 2:
        await message.answer("Dung: /order ORDXXXX")
        return

    order_id = chunks[1].strip()
    order = await db.collections.orders.find_one({"_id": order_id, "user_id": message.from_user.id})
    if not order:
        await message.answer("Khong tim thay don hang.")
        return

    text = "\n".join(
        [
            f"Don: {order['_id']}",
            f"So tien: {order['amount']} VND",
            f"Trang thai: {order['status']}",
            f"Paid: {'Yes' if order.get('paid') else 'No'}",
        ]
    )
    await message.answer(text)
