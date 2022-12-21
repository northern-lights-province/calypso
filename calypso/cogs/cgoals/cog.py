"""
Community goal management for the NLP. These commands can only be run in the NLP server.
"""
from typing import Any

import aiohttp
import disnake
from disnake.ext import commands
from sqlalchemy import delete

from calypso import config, constants, db, models
from calypso.avrae_api.client import AvraeClient
from calypso.errors import UserInputError
from .params import cg_param


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
            name=name, slug=slug, cost_cp=cost_cp, description=description, image_url=image_url
        )

        # TODO: post to cg channel
        new_cg.message_id = msg.id

        # TODO: update avrae gvar

        # add to db
        async with db.async_session() as session:
            session.add(new_cg)
            await session.commit()

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

        # todo: update the CG message
        # TODO: update avrae gvar

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

        # todo: delete the CG message
        # TODO: update avrae gvar

        await inter.send(f"Deleted the goal {cg.name} (`{cg.slug}`).")
