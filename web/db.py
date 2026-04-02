from __future__ import annotations

from dataclasses import dataclass

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from web.config import WebSettings


@dataclass
class WebCollections:
    users: AsyncIOMotorCollection
    products: AsyncIOMotorCollection
    orders: AsyncIOMotorCollection


class WebDatabase:
    def __init__(self, settings: WebSettings):
        self.client = AsyncIOMotorClient(settings.mongo_uri)
        self.db: AsyncIOMotorDatabase = self.client[settings.mongo_db_name]
        self.collections = WebCollections(
            users=self.db["users"],
            products=self.db["products"],
            orders=self.db["orders"],
        )

    async def ping(self) -> None:
        await self.db.command("ping")

    def close(self) -> None:
        self.client.close()
