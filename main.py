from aiogram import Bot, Dispatcher, executor
from config import BOT_TOKEN

from handlers.user import register_user
from handlers.admin import register_admin
from handlers.payment import register_payment

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# register từng module
register_user(dp)
register_admin(dp)
register_payment(dp)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)