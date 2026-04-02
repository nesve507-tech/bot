from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Settings
from bot.db import Database
from bot.services.referral import count_ref_levels

router = Router(name="dashboard")


@router.message(F.text == "Dashboard")
@router.message(F.text == "/dashboard")
async def dashboard_cmd(message: Message, db: Database) -> None:
    user_id = message.from_user.id
    user = await db.collections.users.find_one({"user_id": user_id}) or {"balance": 0}

    total_orders = await db.collections.orders.count_documents({"user_id": user_id})
    done_orders = await db.collections.orders.count_documents({"user_id": user_id, "status": "done"})
    f1, f2, f3 = await count_ref_levels(db.collections.users, user_id)

    me = await message.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}" if me.username else "Bot khong co username"

    text = "\n".join(
        [
            "Thong tin tai khoan:",
            f"- Balance: {int(user.get('balance', 0))} VND",
            f"- Tong don: {total_orders}",
            f"- Don hoan thanh: {done_orders}",
            f"- Ref F1/F2/F3: {f1}/{f2}/{f3}",
            f"- Link ref: {ref_link}",
        ]
    )
    await message.answer(text)


@router.message(Command("withdraw"))
async def withdraw_cmd(message: Message, db: Database, settings: Settings) -> None:
    chunks = message.text.split(maxsplit=1)
    if len(chunks) != 2:
        await message.answer("Dung: /withdraw <so_tien>")
        return

    try:
        amount = int(chunks[1].strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("So tien khong hop le.")
        return

    user_id = message.from_user.id
    user = await db.collections.users.find_one({"user_id": user_id}, {"balance": 1})
    balance = int((user or {}).get("balance", 0))
    if balance < amount:
        await message.answer(f"So du khong du. Balance hien tai: {balance} VND")
        return

    await db.collections.users.update_one(
        {"user_id": user_id, "balance": {"$gte": amount}},
        {"$inc": {"balance": -amount}},
    )

    await db.collections.withdraw_requests.insert_one(
        {
            "user_id": user_id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now(tz=timezone.utc),
        }
    )

    await message.answer("Da tao yeu cau rut tien. Admin se xu ly som.")
    for admin_id in settings.admin_ids:
        await message.bot.send_message(admin_id, f"Yeu cau rut tien moi: user={user_id}, amount={amount} VND")
