from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import Database
from bot.services.payment import check_and_complete_one_order

router = Router(name="payment")


@router.callback_query(F.data.startswith("checkpay_"))
async def check_payment_callback(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    order_id = callback.data.replace("checkpay_", "", 1)
    order = await db.collections.orders.find_one({"_id": order_id, "user_id": callback.from_user.id})
    if not order:
        await callback.answer("Khong tim thay don cua ban.", show_alert=True)
        return

    if order.get("status") == "done":
        await callback.answer("Don nay da hoan thanh.", show_alert=True)
        return

    done = await check_and_complete_one_order(
        bot=callback.bot,
        settings=settings,
        users_col=db.collections.users,
        products_col=db.collections.products,
        orders_col=db.collections.orders,
        order=order,
    )
    if done:
        await callback.answer("Thanh toan da duoc xac nhan.", show_alert=True)
    else:
        await callback.answer("Chua tim thay giao dich phu hop.", show_alert=True)


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
