from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🛒 Sản phẩm"))
    kb.add(KeyboardButton("📦 Đơn của tôi"))
    return kb