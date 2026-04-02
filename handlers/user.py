from aiogram import types
from aiogram.dispatcher import Dispatcher
from db import users
from keyboards.menu import main_menu

def register_user(dp: Dispatcher):

    @dp.message_handler(commands=['start'])
    async def start(msg: types.Message):
        await users.update_one(
            {"user_id": msg.from_user.id},
            {"$set": {"user_id": msg.from_user.id}},
            upsert=True
        )
        await msg.answer("Welcome!", reply_markup=main_menu())