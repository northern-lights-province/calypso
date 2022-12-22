"""
Community goal management for the NLP. These commands can only be run in the NLP server.
"""
import json
from typing import Any

import aiohttp
import disnake
from disnake.ext import commands
from sqlalchemy import delete

from calypso import config, constants, db, models
from calypso.avrae_api.client import AvraeClient
from calypso.errors import UserInputError
from . import queries
from .params import cg_param

# embed color interpolation
CG_START_COLOR = disnake.Colour(0xFFCC99)
CG_END_COLOR = disnake.Colour(0x60D394)
CG_COMPLETE_COLOR = disnake.Colour(0x88AED0)
CG_GVAR_ID = "8c8046fd-5775-49b0-b0ab-1893da5dde5e"


class CommunityGoals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AvraeClient(aiohttp.ClientSession(loop=bot.loop), config.AVRAE_API_KEY)

    # ==== admin commands ====
    @commands.slash_command(name="cg", description="Manage community goals", guild_ids=[constants.GUILD_ID])
    @commands.default_member_permissions(manage_guild=True)
    async def cg(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @cg.sub_command(name="create", description="Create a new community goal")
    async def cg_create(
        self,
        inter: disnake.ApplicationCommandInteraction,
        name: str = commands.Param(desc="The name of the community goal"),
        cost: float = commands.Param(desc="The cost of the CG (in gp)", gt=0),
        slug: str = commands.Param(desc="A short ID for the community goal (e.g. enchanter-t1)"),
        description: str = commands.Param(None, desc="The CG's description"),
        image_url: str = commands.Param(None, desc="The CG's image"),
    ):
        cost_cp = int(cost * 100)
        if not cost_cp > 0:
            raise UserInputError("The goal cost must be at least 0.01gp.")
        new_cg = models.CommunityGoal(
            name=name, slug=slug, cost_cp=cost_cp, description=description, image_url=image_url, funded_cp=0
        )

        # post to cg channel
        msg = await self._send_cg_message(new_cg)
        new_cg.message_id = msg.id

        # add to db
        async with db.async_session() as session:
            session.add(new_cg)
            await session.commit()

        await self._update_avrae_gvar()
        await inter.send(f"Created the community goal {new_cg.name} (`{new_cg.slug}`)!")

    @cg.sub_command(name="edit", description="Edit a community goal")
    async def cg_edit(
        self,
        inter: disnake.ApplicationCommandInteraction,
        cg: Any = cg_param(desc="The community goal to edit"),
        name: str = commands.Param(None, desc="The name of the community goal"),
        cost: float = commands.Param(None, desc="The cost of the CG (in gp)", gt=0),
        slug: str = commands.Param(None, desc="A short ID for the community goal (e.g. enchanter-t1)"),
        description: str = commands.Param(None, desc="The CG's description"),
        image_url: str = commands.Param(None, desc="The CG's image"),
    ):
        async with db.async_session() as session:
            session.add(cg)

            if name is not None:
                cg.name = name
            if cost is not None:
                cost_cp = int(cost * 100)
                if not cost_cp > 0:
                    raise UserInputError("The goal cost must be at least 0.01gp.")
                if cost_cp < cg.funded_cp:
                    raise UserInputError("You cannot set a CG's target to be less than its current funding.")
                cg.cost_cp = cost_cp
            if slug is not None:
                cg.slug = slug
            if description is not None:
                cg.description = description
            if image_url is not None:
                cg.image_url = image_url

            await session.commit()

        await self._edit_cg_message(cg)
        await self._update_avrae_gvar()

        await inter.send(f"Updated the CG {cg.name} (`{cg.slug}`).")

    @cg.sub_command(name="delete", description="Delete a community goal")
    async def cg_delete(
        self,
        inter: disnake.ApplicationCommandInteraction,
        cg: Any = cg_param(desc="The community goal to delete"),
    ):
        async with db.async_session() as session:
            await session.execute(delete(models.CommunityGoal).where(models.CommunityGoal.id == cg.id))
            await session.commit()

        await self._delete_cg_message(cg)
        await self._update_avrae_gvar()

        await inter.send(f"Deleted the goal {cg.name} (`{cg.slug}`).")

    @cg.sub_command(name="debug-fund", description="Fund a CG by an amount (DEBUG ONLY)")
    async def cg_debug_fund(
        self,
        inter: disnake.ApplicationCommandInteraction,
        cg: Any = cg_param(desc="The community goal to fund"),
        amount: float = commands.Param(desc="The amount to change the funding by, in gp"),
    ):
        amt_cp = int(amount * 100)
        async with db.async_session() as session:
            session.add(cg)
            cg.funded_cp += amt_cp
            await session.commit()
        await self._edit_cg_message(cg)
        await self._update_avrae_gvar()
        await inter.send(f"Debug-funded the goal {cg.name} (`{cg.slug}`).")

    # ==== utils ====
    async def _send_cg_message(self, cg: models.CommunityGoal):
        cg_channel = self.bot.get_channel(constants.COMMUNITY_GOAL_CHANNEL_ID)
        return await cg_channel.send(embed=cg_embed(cg))

    async def _edit_cg_message(self, cg: models.CommunityGoal):
        cg_channel = self.bot.get_channel(constants.COMMUNITY_GOAL_CHANNEL_ID)
        msg = cg_channel.get_partial_message(cg.message_id)
        try:
            await msg.edit(embed=cg_embed(cg))
        except disnake.HTTPException:
            pass

    async def _delete_cg_message(self, cg: models.CommunityGoal):
        if cg.message_id is None:
            return
        cg_channel = self.bot.get_channel(constants.COMMUNITY_GOAL_CHANNEL_ID)
        msg = cg_channel.get_partial_message(cg.message_id)
        try:
            await msg.delete()
        except disnake.HTTPException:
            pass

    async def _update_avrae_gvar(self):
        async with db.async_session() as session:
            cgs = await queries.get_all_cgs(session)
        data = [cg.to_dict() for cg in cgs]
        await self.client.set_gvar(CG_GVAR_ID, json.dumps(data))


def cg_embed(cg: models.CommunityGoal) -> disnake.Embed:
    is_finished = cg.funded_cp >= cg.cost_cp
    percent_complete = min(cg.funded_cp / cg.cost_cp, 1)
    if not is_finished:
        start_r, start_g, start_b = CG_START_COLOR.to_rgb()
        end_r, end_g, end_b = CG_END_COLOR.to_rgb()
        dred = end_r - start_r
        dgrn = end_g - start_g
        dblu = end_b - start_b
        color = disnake.Colour.from_rgb(
            start_r + int(dred * percent_complete),
            start_g + int(dgrn * percent_complete),
            start_b + int(dblu * percent_complete),
        )

        n_equals = int(30 * percent_complete)
        n_spaces = 30 - n_equals
        progress_bar = f"```ini\n[{'=' * n_equals}>{' ' * n_spaces}]\n```"
    else:
        color = CG_COMPLETE_COLOR
        progress_bar = "```diff\n+ Goal complete! +\n```"

    embed = disnake.Embed()
    embed.title = cg.name
    embed.colour = color
    embed.description = f"ID: `{cg.slug}`"
    if cg.description is not None:
        embed.description = f"ID: `{cg.slug}`\n*Goal: {cg.description}*"
    embed.add_field(name="Cost", value=f"{cg.cost_cp / 100:,.2f} gp", inline=True)
    embed.add_field(name="Contributed", value=f"{cg.funded_cp / 100:,.2f} gp ({percent_complete:.1%})", inline=True)
    embed.add_field(name="Progress", value=progress_bar, inline=False)
    embed.set_footer(text=f"Contribute to this goal with !cg {cg.slug} <amount>!")
    return embed
