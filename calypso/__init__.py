import disnake
from disnake.ext import commands
from openai import AsyncOpenAI

from . import config


class Calypso(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.openai = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.enc_chatterboxes = dict()

    async def close(self):
        await self.openai.close()
        await super().close()

    async def get_or_fetch_channel(self, channel_id: int):
        """Get a channel or thread by ID, fetching it from the API if not in cache (e.g. archived thread)."""
        channel = self.get_channel(channel_id)
        if channel is not None:
            return channel
        try:
            channel = await self.fetch_channel(channel_id)
        except disnake.NotFound:
            return None
        return channel
