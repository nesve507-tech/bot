from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class AntiSpamService:
    def __init__(self, window_sec: float, max_hits: int):
        self.window_sec = window_sec
        self.max_hits = max_hits
        self._hits: dict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        queue = self._hits[user_id]

        while queue and now - queue[0] > self.window_sec:
            queue.popleft()

        if len(queue) >= self.max_hits:
            return False

        queue.append(now)
        return True


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, anti_spam: AntiSpamService):
        super().__init__()
        self.anti_spam = anti_spam

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        if self.anti_spam.is_allowed(user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer("Ban thao tac qua nhanh. Vui long doi it giay.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Ban bam qua nhanh, thu lai sau nhe.", show_alert=False)
        return None
