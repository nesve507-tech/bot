from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from bson import ObjectId

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


class AddStockState(StatesGroup):
    product = State()
    stock = State()


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


async def _find_product_for_stock(db: Database, raw: str) -> dict | None:
    token = raw.strip()
    if not token:
        return None

    if ObjectId.is_valid(token):
        product = await db.collections.products.find_one({"_id": ObjectId(token)})
        if product:
            return product

    return await db.collections.products.find_one({"name": token})


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
                "- /add_stock",
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


@router.message(Command("add_stock"))
async def add_stock_start(message: Message, settings: Settings, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("Ban khong co quyen.")
        return
    await state.set_state(AddStockState.product)
    await message.answer("Nhap Product ID hoac ten san pham can nap them stock:")


@router.message(AddStockState.product)
async def add_stock_product(message: Message, state: FSMContext, db: Database) -> None:
    product = await _find_product_for_stock(db, message.text)
    if not product:
        await message.answer("Khong tim thay san pham. Nhap lai Product ID hoac ten chinh xac:")
        return

    await state.update_data(product_id=str(product["_id"]), product_name=product["name"])
    await state.set_state(AddStockState.stock)
    await message.answer(
        f"San pham: {product['name']}\n"
        "Nhap stock moi, moi dong 1 item. Co the dung format: content|note"
    )


@router.message(AddStockState.stock)
async def add_stock_items(message: Message, settings: Settings, state: FSMContext, db: Database) -> None:
    if not _is_admin(message.from_user.id, settings):
        await state.clear()
        await message.answer("Ban khong co quyen.")
        return

    data = await state.get_data()
    stock = _parse_stock_lines(message.text)
    if not stock:
        await message.answer("Stock rong. Nhap lai.")
        return

    product_id = data.get("product_id")
    if not product_id or not ObjectId.is_valid(product_id):
        await state.clear()
        await message.answer("Session het han. Vui long /add_stock lai.")
        return

    res = await db.collections.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$push": {"stock": {"$each": stock}}},
    )
    await state.clear()
    if res.modified_count != 1:
        await message.answer("Khong the them stock (san pham co the da bi xoa).")
        return

    await message.answer(
        f"Da them {len(stock)} stock vao san pham {data.get('product_name', product_id)} thanh cong."
    )


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
