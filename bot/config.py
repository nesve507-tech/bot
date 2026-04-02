from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    mongo_uri: str
    mongo_db_name: str
    admin_ids: set[int]

    # VietQR
    vietqr_bank: str
    vietqr_account: str
    vietqr_account_name: str

    # Anti-spam
    anti_spam_window_sec: float
    anti_spam_max_hits: int

    # Payment loop
    payment_check_interval_sec: int
    payment_mock_enabled: bool
    payment_mock_after_sec: int

    # Placeholder fields for real API integration later
    payment_api_url: str | None
    payment_api_key: str | None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int_set(value: str | None) -> set[int]:
    if not value:
        return set()
    result: set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if chunk:
            result.add(int(chunk))
    return result


def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    mongo_uri = os.getenv("MONGO_URI", "").strip()

    if not bot_token:
        raise ValueError("Missing BOT_TOKEN in environment")
    if not mongo_uri:
        raise ValueError("Missing MONGO_URI in environment")

    return Settings(
        bot_token=bot_token,
        mongo_uri=mongo_uri,
        mongo_db_name=os.getenv("MONGO_DB_NAME", "telegram_shop"),
        admin_ids=_as_int_set(os.getenv("ADMIN_IDS", "")),
        vietqr_bank=os.getenv("VIETQR_BANK", "mbbank"),
        vietqr_account=os.getenv("VIETQR_ACCOUNT", "0000000000"),
        vietqr_account_name=os.getenv("VIETQR_ACCOUNT_NAME", "SHOP BOT"),
        anti_spam_window_sec=float(os.getenv("ANTI_SPAM_WINDOW_SEC", "2")),
        anti_spam_max_hits=int(os.getenv("ANTI_SPAM_MAX_HITS", "4")),
        payment_check_interval_sec=int(os.getenv("PAYMENT_CHECK_INTERVAL_SEC", "5")),
        payment_mock_enabled=_as_bool(os.getenv("PAYMENT_MOCK_ENABLED", "true"), True),
        payment_mock_after_sec=int(os.getenv("PAYMENT_MOCK_AFTER_SEC", "15")),
        payment_api_url=os.getenv("PAYMENT_API_URL"),
        payment_api_key=os.getenv("PAYMENT_API_KEY"),
    )
