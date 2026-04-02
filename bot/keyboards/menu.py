from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="San pham"), KeyboardButton(text="Dashboard")],
        [KeyboardButton(text="Don cua toi")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def product_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        stock_count = len(product.get("stock", []))
        builder.button(
            text=f"{product['name']} - {int(product['price'])} VND ({stock_count})",
            callback_data=f"buy_{product['_id']}",
        )
    builder.adjust(1)
    return builder.as_markup()


def payment_kb(order_id: str, qr_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Mo QR", url=qr_url)
    builder.button(text="I have paid", callback_data=f"paid_{order_id}")
    builder.adjust(1)
    return builder.as_markup()
