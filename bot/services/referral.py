from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorCollection

logger = logging.getLogger(__name__)

LEVELS = [
    (1, 0.10),
    (2, 0.05),
    (3, 0.02),
]


async def get_upline(users_col: AsyncIOMotorCollection, user_id: int, depth: int = 3) -> list[int]:
    chain: list[int] = []
    current = user_id

    for _ in range(depth):
        user = await users_col.find_one({"user_id": current}, {"ref_by": 1})
        if not user:
            break

        parent = user.get("ref_by")
        if not isinstance(parent, int):
            break

        chain.append(parent)
        current = parent

    return chain


async def distribute_commission(
    users_col: AsyncIOMotorCollection,
    buyer_id: int,
    order_amount: int,
) -> list[dict[str, int]]:
    upline = await get_upline(users_col, buyer_id, depth=3)
    rewarded: list[dict[str, int]] = []

    for level, ratio in LEVELS:
        if level > len(upline):
            break
        receiver_id = upline[level - 1]
        reward = int(order_amount * ratio)
        if reward <= 0:
            continue

        await users_col.update_one(
            {"user_id": receiver_id},
            {"$inc": {"balance": reward}},
            upsert=True,
        )
        rewarded.append({"user_id": receiver_id, "amount": reward, "level": level})

    if rewarded:
        logger.info(
            "Referral rewards distributed",
            extra={"buyer_id": buyer_id, "order_amount": order_amount, "rewarded": rewarded},
        )

    return rewarded


async def count_ref_levels(users_col: AsyncIOMotorCollection, user_id: int) -> tuple[int, int, int]:
    f1 = [u["user_id"] async for u in users_col.find({"ref_by": user_id}, {"user_id": 1})]
    if not f1:
        return 0, 0, 0

    f2 = [u["user_id"] async for u in users_col.find({"ref_by": {"$in": f1}}, {"user_id": 1})]
    if not f2:
        return len(f1), 0, 0

    f3 = [u["user_id"] async for u in users_col.find({"ref_by": {"$in": f2}}, {"user_id": 1})]
    return len(f1), len(f2), len(f3)
