import aiohttp
from disnake.ext import commands

from . import config
from .openai_api import OpenAIClient


class Calypso(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.openai = OpenAIClient(aiohttp.ClientSession(loop=self.loop), config.OPENAI_API_KEY)

    async def close(self):
        await self.openai.close()
        await super().close()
