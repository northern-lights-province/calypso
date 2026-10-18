"""
2026-10-17
Import Gaius Play XP and replay lost XP from the message log
"""

import asyncio
import csv
import datetime
import os
import sys
from pathlib import Path

import disnake
import tqdm
from sqlalchemy import select, text

from calypso.cogs.xp import XPTracking

sys.path.append(str(Path(__file__).parents[2]))

from calypso import Calypso, constants, db, models

TOKEN = os.getenv("TOKEN")
intents = disnake.Intents.all()


class DuckObject(disnake.Object):
    def __init__(self, id, **kwargs):
        super().__init__(id)
        for k, v in kwargs.items():
            setattr(self, k, v)


async def main():
    bot = Calypso(intents=intents, sync_commands=False, loop=asyncio.get_running_loop())
    bot.loop.create_task(db.init_db())
    await bot.login(TOKEN)
    ws_task = asyncio.create_task(bot.connect())
    await bot.wait_until_ready()

    # import from gaius dump
    print("dump import")
    async with db.async_session() as session:
        await session.execute(text("TRUNCATE TABLE xp_players;"))

        with open("northern_lights_leaderboard_ids.csv", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                xp_obj = models.XPPlayer(
                    guild_id=constants.GUILD_ID,
                    member_id=int(row["user_id"]),
                    xp=int(row["total_xp"]),
                    last_awarded_xp=datetime.datetime(year=1970, month=1, day=1),
                )
                session.add(xp_obj)
        await session.commit()

    # replay logged messages
    guild = bot.get_guild(constants.GUILD_ID)
    xp_cog = XPTracking(bot)

    cutoff_date = datetime.datetime(year=2026, month=10, day=16, hour=17)  # UTC upload time
    stmt = select(models.LoggedMessage).where(
        (models.LoggedMessage.timestamp >= cutoff_date) & (models.LoggedMessage.guild_id == constants.GUILD_ID)
    )
    logged_messages = (await session.execute(stmt)).scalars().all()
    print(f"replay {len(logged_messages)} messages")
    for logged_msg in tqdm.tqdm(logged_messages):
        fake_msg = DuckObject(
            id=logged_msg.message_id,
            author=guild.get_member(logged_msg.author_id),
            guild=guild,
            channel=guild.get_channel_or_thread(logged_msg.channel_id),
            content=logged_msg.content,
            is_system=lambda: False,
        )
        try:
            await xp_cog.on_message(fake_msg)
        except Exception as e:
            print(e)
            # traceback.print_exc()

    await asyncio.sleep(3)
    await bot.close()


if __name__ == "__main__":
    # asyncio.run(main())
    print("to prevent footguns uncomment the main line here")
    print("THIS WILL TRUNCATE THE XP TABLE")
