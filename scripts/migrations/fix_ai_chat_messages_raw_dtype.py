"""
2026-06-06
Fix me saving all raw chat messages as strs containing JSON instead of actual JSON objects
"""
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).parents[2]))

from calypso import db, models


async def main():
    async with db.async_session() as session:
        result = await session.execute(select(models.AIChatMessageRaw))
        msgs = result.scalars().all()

        for msg in msgs:
            if isinstance(msg.data, str):
                msg.data = json.loads(msg.data)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
