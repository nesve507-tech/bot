from __future__ import annotations

import logging
from datetime import datetime

_ACTION_LOGGER = logging.getLogger("bot.action")
_ACTION_LOGGER.setLevel(logging.INFO)
_ACTION_LOGGER.propagate = False

if not _ACTION_LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    _ACTION_LOGGER.addHandler(handler)


def log_action(user_id: int | None, action: str, level: int = logging.INFO) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uid = user_id if user_id is not None else "N/A"
    line = f"[{timestamp}] [USER: {uid}] {action}"
    _ACTION_LOGGER.log(level, line)
