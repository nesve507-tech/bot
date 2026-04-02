from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import Database
from bot.keyboards.menu import main_menu, payment_kb, product_list_kb
from bot.services.delivery import get_product, list_products
from bot.services.payment import build_vietqr_url, create_order

logger = logging.getLogger(__name__)

router = Router(name="user")


def _extract_referrer(start_payload: str | None) -> int | None:
    if not start_payload:
        return None
    payload = start_payload.strip()
    if not payload.startswith("ref_"):
        return None
    try:
        return int(payload.replace("ref_", "", 1))
    except ValueError:
        return None


@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def start_cmd(
    message: Message,
    db: Database,
    settings: Settings,
    command: CommandObject | None = None,
) -> None:
    user_id = message.from_user.id
    referrer = _extract_referrer(command.args if command else None)
    if referrer == user_id:
        referrer = None

    existing = await db.collections.users.find_one({"user_id": user_id}, {"user_id": 1, "ref_by": 1})
    if existing:
        await db.collections.users.update_one(
            {"user_id": user_id},
            {"$set": {"updated_at": datetime.now(tz=timezone.utc)}},
        )
    else:
        await db.collections.users.insert_one(
            {
                "user_id": user_id,
                "ref_by": referrer,
                "balance": 0,
                "created_at": datetime.now(tz=timezone.utc),
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )

    await message.answer(
        "Chao mung ban den voi Shop Bot.\nChon menu ben duoi de xem san pham va mua hang.",
        reply_markup=main_menu(is_admin=user_id in settings.admin_ids),
    )


@router.message(F.text == "San pham")
@router.message(F.text == "/products")
async def list_product_cmd(message: Message, db: Database) -> None:
    products = await list_products(db.collections.products)
    if not products:
        await message.answer("Hien tai chua co san pham nao.")
        return
    await message.answer("Danh sach san pham:", reply_markup=product_list_kb(products))


@router.callback_query(F.data.startswith("buy_"))
async def buy_product_callback(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    product_id = callback.data.replace("buy_", "", 1)
    product = await get_product(db.collections.products, product_id)
    if not product:
        await callback.answer("San pham khong ton tai", show_alert=True)
        return

    if not product.get("stock"):
        await callback.answer("San pham da het stock", show_alert=True)
        return

    order = await create_order(
        orders_col=db.collections.orders,
        user_id=callback.from_user.id,
        product_id=product_id,
        amount=int(product["price"]),
    )
    qr_url = build_vietqr_url(settings, amount=int(product["price"]), order_id=order["_id"])

    await callback.message.answer(
        "\n".join(
            [
                f"Da tao don: {order['_id']}",
                f"San pham: {product['name']}",
                f"So tien: {int(product['price'])} VND",
                "Noi dung CK: dung chinh xac ma don hang.",
                f"Noi dung: {order['_id']}",
                "Sau khi chuyen khoan, nhan 'I have paid' de bao admin duyet don.",
            ]
        ),
        reply_markup=payment_kb(order_id=order["_id"], qr_url=qr_url),
    )
    await callback.answer("Da tao don hang")
    logger.info("Order created", extra={"order_id": order["_id"], "user_id": callback.from_user.id})


@router.message(F.text == "Don cua toi")
async def my_orders_cmd(message: Message, db: Database) -> None:
    cursor = db.collections.orders.find({"user_id": message.from_user.id}).sort("created_at", -1).limit(10)
    orders = [order async for order in cursor]
    if not orders:
        await message.answer("Ban chua co don hang nao.")
        return

    lines = ["10 don gan nhat cua ban:"]
    for o in orders:
        lines.append(f"- {o['_id']} | {o['amount']} VND | {o['status']}")
    await message.answer("\n".join(lines))
