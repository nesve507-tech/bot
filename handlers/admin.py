from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import ADMIN_ID
from db import products

class AddProduct(StatesGroup):
    name = State()
    price = State()
    stock = State()

def register_admin(dp: Dispatcher):

    @dp.message_handler(commands=['add'], user_id=ADMIN_ID)
    async def add_start(msg: types.Message):
        await msg.answer("Nhập tên sản phẩm:")
        await AddProduct.name.set()

    @dp.message_handler(state=AddProduct.name)
    async def add_name(msg: types.Message, state: FSMContext):
        await state.update_data(name=msg.text)
        await msg.answer("Nhập giá:")
        await AddProduct.price.set()

    @dp.message_handler(state=AddProduct.price)
    async def add_price(msg: types.Message, state: FSMContext):
        await state.update_data(price=int(msg.text))
        await msg.answer("Nhập stock (mỗi dòng 1 acc):")
        await AddProduct.stock.set()

    @dp.message_handler(state=AddProduct.stock)
    async def add_stock(msg: types.Message, state: FSMContext):
        data = await state.get_data()

        stock_list = msg.text.split("\n")

        await products.insert_one({
            "name": data["name"],
            "price": data["price"],
            "stock": stock_list
        })

        await msg.answer("✅ Đã thêm sản phẩm")
        await state.finish()