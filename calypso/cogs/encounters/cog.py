"""
Random encounter tables for the NLP. These commands can only be run in the NLP server.
"""
import re
from bisect import bisect_left

import d20
import disnake
from disnake.ext import commands

from calypso import constants
from .client import EncounterClient, EncounterRepository
from .params import biome_param


class Encounters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = EncounterClient()
        self.bot.loop.create_task(self.client.refresh_encounters())

    @commands.slash_command(description="Rolls a random encounter.", guild_ids=[constants.GUILD_ID])
    async def enc(
        self,
        inter: disnake.ApplicationCommandInteraction,
        biome: str = biome_param(desc="The biome to roll an encounter in."),
        tier: int = commands.Param(gt=0, desc="The encounter tier to roll."),
        private: bool = commands.Param(False, desc="Whether to send the result as a private message or not."),
    ):
        # find the biome and tier
        tier_obj = next((t for t in EncounterRepository.tiers if t.biome == biome and t.tier == tier), None)
        if tier_obj is None:
            return await inter.send(f"I couldn't find an encounter table for {biome}, tier {tier}.", ephemeral=private)

        # choose a random encounter
        # alg derived from random.randchoices
        min_nonzero_weight = min(w for w in tier_obj.encounter_weights if w > 0)
        normalized_weights = [round(w / min_nonzero_weight) for w in tier_obj.encounter_cum_weights]
        roll_result = d20.roll(f"1d{normalized_weights[-1]}")
        idx = bisect_left(normalized_weights, roll_result.total)
        encounter = tier_obj.encounters[idx]

        # render the encounter text
        encounter_text = re.sub(r"\{.+?}", lambda match: d20.roll(match.group(1)).result, encounter.text)

        # roll the encounter template dice
        embed = disnake.Embed(
            title="Rolling for random encounter...",
            description=f"**{biome} - Tier {tier}**\nRoll: {roll_result}\n\n{encounter_text}",
            colour=disnake.Colour.random(),
        )
        await inter.send(embed=embed, ephemeral=private)

    # ==== admin ====
    @commands.slash_command(description="Reload the encounter repository", guild_ids=[constants.GUILD_ID])
    @commands.default_member_permissions(manage_guild=True)
    async def reload_encounters(self, inter: disnake.ApplicationCommandInteraction):
        await self.client.refresh_encounters()
        n_encounters = sum(len(t.encounters) for t in EncounterRepository.tiers)
        n_tiers = len(EncounterRepository.tiers)
        await inter.send(f"Refreshed encounters - loaded {n_encounters} encounters across {n_tiers} biome-tiers")
