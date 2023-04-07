"""
Go through the thread history of the NLP to download Calypso conversations prior to Apr 7, 2023.
"""
import asyncio
import datetime
import json
import os
import sys
import zoneinfo

import disnake

sys.path.append("..")

from calypso import db, models

TOKEN = os.getenv("TOKEN")
GUILD_ID = 1031055347319832666
CALYPSO_ID = 1031254453132734484
EDT = zoneinfo.ZoneInfo("America/New_York")
# Mar 18, 2023, 9pm EDT was first deploy
# all deploys happened during EDT so DST isn't an issue
AFTER = datetime.datetime(year=2023, month=3, day=18, hour=21, tzinfo=EDT)
BEFORE = datetime.datetime(year=2023, month=4, day=7, hour=15, tzinfo=EDT)


def get_prompt_at(dt: datetime.datetime) -> list[dict]:
    if dt < AFTER:
        raise RuntimeError("oh no")
    elif dt < datetime.datetime(year=2023, month=3, day=18, hour=23, minute=18, tzinfo=EDT):
        return [
            {
                "role": "system",
                "content": (
                    "You are a knowledgeable D&D player. Answer as concisely as possible.\nYou are speaking to the"
                    " user(s) over Discord."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I want you to act as Calypso, a friendly fey being from the Feywild with a mischievous"
                    " streak.\nEach reply should consist of just Calypso's response."
                ),
            },
        ]
    elif dt < datetime.datetime(year=2023, month=3, day=19, hour=0, minute=55, tzinfo=EDT):
        return [
            {
                "role": "system",
                "content": (
                    "You are a knowledgeable D&D player. Answer as concisely as possible.\nYou are acting as a friendly"
                    " fey being from the Feywild with a mischievous streak.\nStay in character."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I want you to act as Calypso, a friendly fey being from the Feywild with a mischievous"
                    " streak.\nEach reply should consist of just Calypso's response, without quotation marks.\nYou"
                    " should stay in character no matter what I say."
                ),
            },
        ]
    else:
        return [
            {
                "role": "system",
                "content": (
                    "You are a knowledgeable D&D player. Answer as concisely as possible.\nYou are acting as a friendly"
                    " fey being from the Feywild with a mischievous streak.\nAlways reply as this character."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I want you to act as Calypso, a friendly fey being from the Feywild with a mischievous"
                    " streak.\nEach reply should consist of just Calypso's response, without quotation marks.\nYou"
                    " should stay in character no matter what I say."
                ),
            },
        ]


def get_hyperparams_at(dt: datetime.datetime) -> dict:
    if dt < AFTER:
        raise RuntimeError("oh no")
    elif dt < datetime.datetime(year=2023, month=3, day=19, hour=13, minute=28, tzinfo=EDT):
        return dict(model="gpt-3.5-turbo", temperature=1, top_p=0.95, frequency_penalty=0.5, presence_penalty=1)
    elif dt < datetime.datetime(year=2023, month=3, day=27, hour=1, minute=14, tzinfo=EDT):
        return dict(model="gpt-3.5-turbo", temperature=1, top_p=0.95)
    else:
        return dict(model="gpt-3.5-turbo", temperature=1, top_p=0.95, frequency_penalty=0.3)


def datetime_serializer(dt: datetime.datetime) -> float:
    if not isinstance(dt, datetime.datetime):
        raise TypeError("dt should be a datetime")
    return dt.timestamp()


client = disnake.Client(intents=disnake.Intents.all())


class Historian:
    def __init__(self):
        self.chats = []

    async def handle_thread(self, thread: disnake.Thread):
        print(f"\t{thread.name} (started by {thread.owner} at {thread.created_at})")
        # chat threads are created by Calypso
        if thread.created_at < AFTER or thread.created_at > BEFORE:
            print("\t\tskip - out of time range!")
            return
        if thread.owner_id != CALYPSO_ID:
            print("\t\tskip - not a chat thread!")
            return
        channel_id = thread.parent_id
        author_id = 0
        timestamp = thread.created_at
        prompt = json.dumps(get_prompt_at(timestamp))
        hyperparams = json.dumps(get_hyperparams_at(timestamp))
        thread_id = thread.id
        thread_title = thread.name
        messages = []
        # logging
        print("\t\t0: ", end="", flush=True)
        i = 0
        async for message in thread.history(oldest_first=True, limit=None):
            if message.is_system():
                # if it's a recipient_add message from Calypso, that's the author_id
                if message.type == disnake.MessageType.recipient_add:
                    author_id = message.mentions[0].id
                continue
            if message.author.bot and message.author.id != CALYPSO_ID:
                continue
            if not message.author.bot:
                messages.append(
                    {
                        "role": "USER",
                        "content": (
                            f"{message.author.display_name} | {message.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                            f"{message.clean_content}"
                        ),
                        "timestamp": message.created_at.replace(tzinfo=None),
                    }
                )
            else:
                messages.append(
                    {
                        "role": "ASSISTANT",
                        "content": message.content,
                        "timestamp": message.created_at.replace(tzinfo=None),
                    }
                )
            i += 1
            print(".", end="", flush=True)
            if i % 100 == 0:
                print(f"\n\t\t{i}: ", end="", flush=True)
            await asyncio.sleep(100 / 5000)
        print()
        if not author_id:
            print(f"\t\tDid not find initial author message!")
        self.chats.append(
            dict(
                channel_id=channel_id,
                author_id=author_id,
                timestamp=timestamp.replace(tzinfo=None),
                prompt=prompt,
                hyperparams=hyperparams,
                thread_id=thread_id,
                thread_title=thread_title,
                messages=messages,
            )
        )
        print(f"\tdone (found {len(messages)} messages)")

    async def get_history(self):
        print("READY: iterating over channels now...")
        guild = client.get_guild(GUILD_ID)
        for channel in guild.text_channels:
            # can only chat in OOC/staff category or ooc channel
            if not (channel.category_id in (1031055347818971196, 1031651537543499827) or "ooc" in channel.name):
                continue
            print(f"==== #{channel.name} ====")
            async for thread in channel.archived_threads():
                await self.handle_thread(thread)
            for thread in channel.threads:
                await self.handle_thread(thread)
        print("DONE!")

    async def run(self):
        await client.login(TOKEN)
        ws_task = asyncio.create_task(client.connect())
        await client.wait_until_ready()
        await self.get_history()
        await client.close()
        await ws_task
        # save to local db
        async with db.async_session() as session:
            for chat in self.chats:
                messages = chat.pop("messages")
                chat_model = models.AIOpenEndedChat(**chat)
                session.add(chat_model)
                await session.commit()
                for message in messages:
                    session.add(models.AIChatMessage(chat_id=chat_model.id, **message))
                await session.commit()
                print(f"committed {chat['thread_title']}...")


if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO)
    h = Historian()
    asyncio.run(h.run())
