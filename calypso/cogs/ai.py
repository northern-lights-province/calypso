import asyncio

import aiohttp
import disnake
from disnake.ext import commands

from calypso import config, constants
from calypso.openai_api import OpenAIClient
from calypso.utils.functions import chunk_text

ABILITY_AUTOMATION_MODEL = "curie:ft-ccb-lab-members-2022-12-25-19-34-58"


class AIUtils(commands.Cog):
    """Various AI utilities for players and DMs."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.client = OpenAIClient(aiohttp.ClientSession(loop=bot.loop), config.OPENAI_API_KEY)

    @commands.slash_command(name="ai", description="AI utilities", guild_ids=[constants.GUILD_ID])
    async def ai(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ai.sub_command_group(name="text2auto")
    async def ai_text2auto(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ai_text2auto.sub_command(name="monster", description="Generate automation for a monster's ability (2 steps).")
    async def ai_text2auto_monster(
        self,
        inter: disnake.ApplicationCommandInteraction,
        monster: str = commands.Param(desc="The name of the monster."),
        ability: str = commands.Param(desc="The name of the ability."),
        critterdb_format: bool = commands.Param(True, desc="Whether to return CritterDB override syntax."),
    ):
        # Discord pls add multiline text inputs
        # it's been years
        # :(
        await inter.response.send_modal(
            title=f"{monster}: {ability}",
            custom_id=str(inter.id),
            components=disnake.ui.TextInput(
                label="Paste the ability's full description",
                custom_id="value",
                style=disnake.TextInputStyle.paragraph,
                max_length=1900,
            ),
        )
        try:
            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                "modal_submit", check=lambda mi: mi.custom_id == str(inter.id), timeout=600
            )
        except asyncio.TimeoutError:
            return
        ability_text = modal_inter.text_values["value"]
        await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
        await modal_inter.channel.trigger_typing()

        # build prompt and query GPT-3
        prompt = f"{monster}: {ability}\n{ability_text}\n###\n"
        completion = await self.client.create_completion(
            model=ABILITY_AUTOMATION_MODEL,
            prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
            stop=["\n^^^"],
            top_p=0.95,
            user=str(inter.author.id),
        )
        automation = completion.text
        if critterdb_format:
            automation_chunks = chunk_text(
                f"<avrae hidden>\nname: {ability}\n_v: 2\nautomation:\n{automation}\n</avrae>",
                max_chunk_size=1900,
                chunk_on=("\n",),
            )
        else:
            automation_chunks = chunk_text(automation, max_chunk_size=1900, chunk_on=("\n",))

        for chunk in automation_chunks:
            await modal_inter.channel.send(f"```yaml\n{chunk}\n```")


def setup(bot):
    bot.add_cog(AIUtils(bot))
