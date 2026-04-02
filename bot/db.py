from __future__ import annotations

import logging
from dataclasses import dataclass

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING

from bot.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Collections:
    users: AsyncIOMotorCollection
    products: AsyncIOMotorCollection
    orders: AsyncIOMotorCollection
    withdraw_requests: AsyncIOMotorCollection


class Database:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncIOMotorClient(settings.mongo_uri)
        self._db: AsyncIOMotorDatabase = self._client[settings.mongo_db_name]
        self.collections = Collections(
            users=self._db["users"],
            products=self._db["products"],
            orders=self._db["orders"],
            withdraw_requests=self._db["withdraw_requests"],
        )

    @property
    def db(self) -> AsyncIOMotorDatabase:
        return self._db

    async def ensure_indexes(self) -> None:
        # Keep unique constraints and query paths fast under production load.
        await self.collections.users.create_index([("user_id", ASCENDING)], unique=True)
        await self.collections.users.create_index([("ref_by", ASCENDING)])

        await self.collections.products.create_index([("name", ASCENDING)], unique=True)

        await self.collections.orders.create_index([("_id", ASCENDING)], unique=True)
        await self.collections.orders.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
        await self.collections.orders.create_index([("status", ASCENDING), ("paid", ASCENDING)])

        await self.collections.withdraw_requests.create_index([("user_id", ASCENDING), ("status", ASCENDING)])

        logger.info("MongoDB indexes ensured")

    async def ping(self) -> None:
        await self._db.command("ping")

    def close(self) -> None:
        self._client.close()
