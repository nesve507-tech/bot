from aiogram import types
from aiogram.dispatcher import Dispatcher

def register_payment(dp: Dispatcher):

    @dp.message_handler(commands=['pay'])
    async def pay(msg: types.Message):
        await msg.answer("Thanh toán tại đây...")