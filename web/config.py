from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class WebSettings:
    mongo_uri: str
    mongo_db_name: str
    admin_key: str
    session_secret: str


def get_settings() -> WebSettings:
    mongo_uri = os.getenv("MONGO_URI", "").strip()
    admin_key = os.getenv("WEB_ADMIN_KEY", "").strip()
    if not mongo_uri:
        raise ValueError("Missing MONGO_URI in environment")
    if not admin_key:
        raise ValueError("Missing WEB_ADMIN_KEY in environment")

    return WebSettings(
        mongo_uri=mongo_uri,
        mongo_db_name=os.getenv("MONGO_DB_NAME", "telegram_shop").strip() or "telegram_shop",
        admin_key=admin_key,
        session_secret=(os.getenv("WEB_SESSION_SECRET", "change-me-session-secret").strip() or "change-me-session-secret"),
    )
