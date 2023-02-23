import asyncio

import disnake
from disnake.ext import commands

from calypso import Calypso, constants
from calypso.utils.functions import chunk_text, multiline_modal


class AIUtils(commands.Cog):
    """Various AI utilities for players and DMs."""

    def __init__(self, bot):
        self.bot: Calypso = bot

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
        try:
            modal_inter, ability_text = await multiline_modal(
                inter, title=f"{monster}: {ability}", label="Paste the ability's full description", timeout=600
            )
        except asyncio.TimeoutError:
            return
        await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
        await modal_inter.channel.trigger_typing()

        # build prompt and query GPT-3
        prompt = f"{monster}: {ability}\n{ability_text}\n###\n"
        completion = await self.bot.openai.create_completion(
            model=constants.ABILITY_AUTOMATION_MODEL,
            prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
            stop=["\n^^^"],
            top_p=0.95,
            user=str(inter.author.id),
        )
        automation = completion.text.strip()
        if automation == "meta: No automation":
            automation_chunks = ["No automation was generated. Perhaps this ability doesn't need automation."]
        elif critterdb_format:
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
