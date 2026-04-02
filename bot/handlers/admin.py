from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Settings
from bot.db import Database
from bot.keyboards.menu import main_menu
from bot.services.payment import complete_order

logger = logging.getLogger(__name__)

router = Router(name="admin")


class AddProductState(StatesGroup):
    name = State()
    price = State()
    stock = State()


class BroadcastState(StatesGroup):
    body = State()


def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


def _parse_stock_lines(raw: str) -> list[dict[str, str]]:
    """
    Stock format:
    - Basic: account:pass
    - Extended: account:pass|optional note
    """
    result: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            content, note = line.split("|", 1)
            result.append({"content": content.strip(), "note": note.strip()})
        else:
            result.append({"content": line})
    return result


@router.message(F.text == "Admin Panel")
@router.message(Command("admin"))
async def admin_panel_cmd(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return
    await message.answer(
        "\n".join(
            [
                "Admin commands:",
                "- /add_product",
                "- /approve ORDXXXX",
                "- /broadcast",
                "- /stats",
            ]
        ),
        reply_markup=main_menu(is_admin=True),
    )


@router.message(Command("add_product"))
async def add_product_start(message: Message, state: FSMContext, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return
    await state.set_state(AddProductState.name)
    await message.answer("Nhap ten san pham:")


@router.message(AddProductState.name)
async def add_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductState.price)
    await message.answer("Nhap gia (VND):")


@router.message(AddProductState.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Gia khong hop le. Nhap lai so nguyen duong:")
        return

    await state.update_data(price=price)
    await state.set_state(AddProductState.stock)
    await message.answer("Nhap stock, moi dong 1 item. Co the dung format: content|note")


@router.message(AddProductState.stock)
async def add_product_stock(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    stock = _parse_stock_lines(message.text)
    if not stock:
        await message.answer("Stock rong. Nhap lai.")
        return

    try:
        await db.collections.products.insert_one(
            {
                "name": data["name"],
                "price": int(data["price"]),
                "stock": stock,
                "created_at": datetime.now(tz=timezone.utc),
            }
        )
    except Exception:
        await state.clear()
        await message.answer("Them san pham that bai (co the trung ten).")
        return

    await state.clear()
    await message.answer("Them san pham thanh cong.")


@router.message(Command("approve"))
async def approve_order_cmd(message: Message, settings: Settings, db: Database) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return

    chunks = message.text.split(maxsplit=1)
    if len(chunks) != 2:
        await message.answer("Dung: /approve ORDXXXX")
        return

    order_id = chunks[1].strip()
    done = await complete_order(
        bot=message.bot,
        users_col=db.collections.users,
        products_col=db.collections.products,
        orders_col=db.collections.orders,
        order_id=order_id,
        source=f"admin_{message.from_user.id}",
    )
    await message.answer("Da approve don hang." if done else "Approve that bai (co the don khong ton tai/het stock).")


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, settings: Settings, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return
    await state.set_state(BroadcastState.body)
    await message.answer("Nhap noi dung can broadcast:")


@router.message(BroadcastState.body)
async def broadcast_body(message: Message, settings: Settings, state: FSMContext, db: Database) -> None:
    if not _is_admin(message.from_user.id, settings):
        await state.clear()
        await message.answer("Ban khong co quyen.")
        return

    sent = 0
    failed = 0
    async for user in db.collections.users.find({}, {"user_id": 1}):
        uid = user["user_id"]
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(f"Broadcast xong. Sent={sent}, Failed={failed}")


@router.message(Command("stats"))
async def admin_stats_cmd(message: Message, settings: Settings, db: Database) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return

    total_users = await db.collections.users.count_documents({})
    total_orders = await db.collections.orders.count_documents({})
    done_orders = await db.collections.orders.count_documents({"status": "done"})

    pipeline = [
        {"$match": {"status": "done"}},
        {"$group": {"_id": None, "revenue": {"$sum": "$amount"}}},
    ]
    agg = [item async for item in db.collections.orders.aggregate(pipeline)]
    revenue = int(agg[0]["revenue"]) if agg else 0

    await message.answer(
        "\n".join(
            [
                "Thong ke he thong:",
                f"- Users: {total_users}",
                f"- Orders: {total_orders}",
                f"- Done orders: {done_orders}",
                f"- Revenue: {revenue} VND",
            ]
        )
    )
