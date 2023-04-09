import aiohttp
import disnake
from disnake.ext import commands

from . import config
from .openai_api import OpenAIClient


class Calypso(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.openai = OpenAIClient(aiohttp.ClientSession(loop=self.loop), config.OPENAI_API_KEY)
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
