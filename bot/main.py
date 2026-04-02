from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.db import Database
from bot.handlers.admin import router as admin_router
from bot.handlers.dashboard import router as dashboard_router
from bot.handlers.payment import router as payment_router
from bot.handlers.user import router as user_router
from bot.services.anti_spam import AntiSpamMiddleware, AntiSpamService


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def run() -> None:
    configure_logging()
    settings = get_settings()
    db = Database(settings)

    await db.ping()
    await db.ensure_indexes()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    anti_spam = AntiSpamService(
        window_sec=settings.anti_spam_window_sec,
        max_hits=settings.anti_spam_max_hits,
    )
    middleware = AntiSpamMiddleware(anti_spam)
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)

    dp.include_routers(user_router, dashboard_router, payment_router, admin_router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        logging.getLogger(__name__).exception("Unhandled bot error", exc_info=event.exception)
        update = event.update
        message = getattr(update, "message", None)
        callback = getattr(update, "callback_query", None)
        if message:
            await message.answer("He thong dang ban. Vui long thu lai sau.")
        elif callback:
            await callback.answer("Co loi xay ra, thu lai sau.", show_alert=True)
        return True

    try:
        await dp.start_polling(bot, db=db, settings=settings)
    finally:
        db.close()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
