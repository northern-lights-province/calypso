"""
Random encounter tables for the NLP. These commands can only be run in the NLP server.
"""
import asyncio
import re
from bisect import bisect_left

import d20
import disnake
from disnake.ext import commands

from calypso import Calypso, constants, db, models
from calypso.utils.functions import multiline_modal
from . import matcha, queries
from .ai import EncounterHelperController
from .client import EncounterClient, EncounterRepository
from .params import biome_param


class Encounters(commands.Cog):
    def __init__(self, bot: Calypso):
        self.bot = bot
        self.client = EncounterClient()
        self.bot.loop.create_task(self.client.refresh_encounters())

    @commands.slash_command(description="Rolls a random encounter.", guild_ids=[constants.GUILD_ID])
    async def enc(
        self,
        inter: disnake.ApplicationCommandInteraction,
        tier: int = commands.Param(gt=0, desc="The encounter tier to roll."),
        biome: str = biome_param(None, desc="The biome to roll an encounter in (disables AI assist features)."),
        private: bool = commands.Param(True, desc="Whether to send the result as a private message or not."),
    ):
        # get biome from channel link
        if biome is None:
            async with db.async_session() as session:
                echannel = await queries.get_encounter_channel(session, inter.channel_id)
                if echannel is None:
                    return await inter.send(
                        f"This channel does not have a linked encounter table. Please roll in the in-character channel,"
                        f" or supply the `biome` argument."
                    )
                biome = echannel.enc_table_name
        else:
            echannel = None

        # find the biome and tier
        biome_tiers = [t for t in EncounterRepository.tiers if t.biome == biome]
        if not biome_tiers:
            return await inter.send(f"I couldn't find a biome named {biome!r}.", ephemeral=private)
        tier_obj = next((t for t in biome_tiers if t.tier == tier), None)
        if tier_obj is None:
            available_tiers = ", ".join(str(t.tier) for t in biome_tiers)
            return await inter.send(
                f"I couldn't find an encounter table for {biome}, tier {tier} (available tiers: {available_tiers}).",
                ephemeral=private,
            )

        # choose a random encounter
        # alg derived from random.randchoices
        min_nonzero_weight = min(w for w in tier_obj.encounter_weights if w > 0)
        normalized_weights = [round(w / min_nonzero_weight) for w in tier_obj.encounter_cum_weights]
        roll_result = d20.roll(f"1d{normalized_weights[-1]}")
        idx = bisect_left(normalized_weights, roll_result.total)
        encounter = tier_obj.encounters[idx]

        # render the encounter text
        encounter_text = encounter.text
        # monster links
        referenced_monsters = matcha.extract_monsters(encounter.text)
        for mon, pos in matcha.list_to_pairs(referenced_monsters):
            encounter_text = encounter_text[:pos] + f"[{mon.name}]({mon.url})" + encounter_text[pos + len(mon.name) :]
        # rolls
        encounter_text = re.sub(r"\{(.+?)}", lambda match: d20.roll(match.group(1)).result, encounter_text)

        # save the encounter to db
        async with db.async_session() as session:
            rolled_encounter = models.RolledEncounter(
                channel_id=inter.channel_id,
                author_id=inter.author.id,
                table_name=biome,
                tier=tier,
                rendered_text=encounter_text,
                monster_ids=",".join(map(str, (m.id for m, _ in referenced_monsters))),
                biome_name=echannel.name if echannel else None,
                biome_text=echannel.desc if echannel else None,
            )
            session.add(rolled_encounter)
            await session.commit()

        # send the message, with options for AI assist
        embed = disnake.Embed(
            title="Rolling for random encounter...",
            description=f"**{biome} - Tier {tier}**\nRoll: {roll_result}\n\n{encounter_text}",
            colour=disnake.Colour.random(),
        )

        # set up AI helper if in ic channel and matched monsters (todo: maybe not necessary)
        ai_helper = None
        if echannel and referenced_monsters:
            ai_helper = EncounterHelperController(
                inter.author, encounter=rolled_encounter, monsters=[m for m, _ in referenced_monsters], embed=embed
            )

        # and send message
        if ai_helper:
            # message control is deferred to the ai controller here
            await inter.send(embed=embed, ephemeral=private, view=ai_helper)
        else:
            await inter.send(embed=embed, ephemeral=private)

        # if the encounter was private, send a copy to the staff log
        if private:
            log_channel = self.bot.get_channel(constants.STAFF_LOG_CHANNEL_ID)
            await log_channel.send(
                f"{inter.author.mention} rolled a hidden encounter in {inter.channel.mention}:",
                embed=embed,
                allowed_mentions=disnake.AllowedMentions.none(),
            )

    # ==== admin ====
    @commands.slash_command(description="Reload the encounter repository", guild_ids=[constants.GUILD_ID])
    @commands.default_member_permissions(manage_guild=True)
    async def reload_encounters(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        await self.client.refresh_encounters()
        n_encounters = sum(len(t.encounters) for t in EncounterRepository.tiers)
        n_tiers = len(EncounterRepository.tiers)
        await inter.send(f"Refreshed encounters - loaded {n_encounters} encounters across {n_tiers} biome-tiers")

    @commands.slash_command(name="encadmin", description="Create/remove channel links", guild_ids=[constants.GUILD_ID])
    @commands.default_member_permissions(manage_guild=True)
    async def encadmin(self, inter: disnake.ApplicationCommandInteraction):
        pass

    # ---- channel ----
    @encadmin.sub_command_group(name="channel")
    async def encadmin_channel(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @encadmin_channel.sub_command(name="setup", description="Set up an encounter channel.")
    async def encadmin_channel_setup(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(desc="The text channel for the biome"),
        name: str = commands.Param(desc="The name of the biome"),
        recommended_level: str = commands.Param(desc="The recommended level for the biome"),
        onward_travel: str = commands.Param(desc="The channels this biome links to"),
        image_url: str = commands.Param(None, desc="The image URL for the biome"),
        enc_table: str = biome_param(desc="The encounter table for this biome"),
    ):
        async with db.async_session() as session:
            existing = await queries.get_encounter_channel(session, channel.id)
            if existing:
                return await inter.send("This channel has already been set up. Use `/encadmin channel edit` instead.")
            # get the channel desc
            try:
                inter, desc = await multiline_modal(
                    inter, title=f"{name}: Channel Description", label="Description", max_length=1500, timeout=600
                )
            except asyncio.TimeoutError:
                return

            # set up obj
            new_channel = models.EncounterChannel(
                channel_id=channel.id,
                name=name,
                desc=desc,
                recommended_level=recommended_level,
                onward_travel=onward_travel,
                image_url=image_url,
                enc_table_name=enc_table,
                pinned_message_id=0,
            )

            # send the pinned message
            message = await _send_encchannel_message(channel, new_channel)

            # record to db
            new_channel.pinned_message_id = message.id
            session.add(new_channel)
            await session.commit()
        await inter.send(f"OK, created {name} in {channel.mention}.")

    @encadmin_channel.sub_command(name="list", description="List the managed encounter channels.")
    async def encadmin_channel_list(self, inter: disnake.ApplicationCommandInteraction):
        async with db.async_session() as session:
            echannels = await queries.get_all_encounter_channels(session)
        if not echannels:
            await inter.send("This server has no managed encounter channels. Make some with `/encadmin channel setup`.")
            return
        await inter.send("\n".join(f"<#{echannel.channel_id}> - {echannel.name}" for echannel in echannels))

    @encadmin_channel.sub_command(
        name="edit", description="Edit an encounter channel. To edit description use /encadmin channel edit-desc."
    )
    async def encadmin_channel_edit(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(desc="The text channel for the biome"),
        name: str = commands.Param(None, desc="The name of the biome"),
        recommended_level: str = commands.Param(None, desc="The recommended level for the biome"),
        onward_travel: str = commands.Param(None, desc="The channels this biome links to"),
        image_url: str = commands.Param(None, desc="The image URL for the biome"),
        enc_table: str = biome_param(None, desc="The encounter table for this biome"),
    ):
        async with db.async_session() as session:
            existing = await queries.get_encounter_channel(session, channel.id)
            if not existing:
                return await inter.send("This channel has not been set up. Use `/encadmin channel setup` instead.")

            if name is not None:
                existing.name = name
            if recommended_level is not None:
                existing.recommended_level = recommended_level
            if onward_travel is not None:
                existing.onward_travel = onward_travel
            if image_url is not None:
                existing.image_url = image_url
            if enc_table is not None:
                existing.enc_table = enc_table

            await _edit_encchannel_message(channel, existing)
            await session.commit()
        await inter.send(f"OK, edited {existing.name} in {channel.mention}.")

    @encadmin_channel.sub_command(
        name="edit-desc",
        description="Edit an encounter channel description. To edit other details use /encadmin channel edit.",
    )
    async def encadmin_channel_edit_desc(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(desc="The text channel for the biome"),
    ):
        async with db.async_session() as session:
            existing = await queries.get_encounter_channel(session, channel.id)
            if not existing:
                return await inter.send("This channel has not been set up. Use `/encadmin channel setup` instead.")

            # get the channel desc
            try:
                inter, desc = await multiline_modal(
                    inter,
                    title=f"{existing.name}: Channel Description",
                    label="Description",
                    max_length=1500,
                    timeout=600,
                )
            except asyncio.TimeoutError:
                return

            existing.desc = desc
            await _edit_encchannel_message(channel, existing)
            await session.commit()
        await inter.send(f"OK, edited {existing.name} in {channel.mention}.")

    @encadmin_channel.sub_command(name="delete", description="Stop tracking a managed encounter channel")
    async def encadmin_channel_delete(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(desc="A text channel to delete the encounter info of"),
    ):
        async with db.async_session() as session:
            enc = await queries.get_encounter_channel(session, channel.id)
            if enc is None:
                return await inter.send("This channel is not set up.")
            # unpin the pinned message
            msg = channel.get_partial_message(enc.pinned_message_id)
            try:
                await msg.unpin()
            except disnake.HTTPException:
                pass
            # and delete from db
            await queries.delete_encounter_channel(session, channel.id)
            await session.commit()
        await inter.send(f"Deleted the managed encounter channel in {channel.mention}.")


async def _send_encchannel_message(channel: disnake.TextChannel, encounter_channel: models.EncounterChannel):
    embed = None
    if encounter_channel.image_url:
        embed = disnake.Embed()
        embed.set_image(encounter_channel.image_url)
    quoted_desc = "\n".join(f"> {line}" for line in encounter_channel.desc.strip().splitlines())
    message = await channel.send(
        (
            f"**__{encounter_channel.name}__**\n"
            f"{quoted_desc}\n\n"
            f"**Recommended Level**: {encounter_channel.recommended_level}\n"
            f"**Table**: {encounter_channel.enc_table_name} (`/enc <tier>`)\n"
            f"**Onward Travel**: {encounter_channel.onward_travel}"
        ),
        embed=embed,
    )
    await message.pin()
    return message


async def _edit_encchannel_message(
    channel: disnake.TextChannel, encounter_channel: models.EncounterChannel, recreate_if_missing=True
):
    msg = channel.get_partial_message(encounter_channel.pinned_message_id)
    embed = None
    if encounter_channel.image_url:
        embed = disnake.Embed()
        embed.set_image(encounter_channel.image_url)
    quoted_desc = "\n".join(f"> {line}" for line in encounter_channel.desc.strip().splitlines())
    try:
        await msg.edit(
            (
                f"**__{encounter_channel.name}__**\n"
                f"{quoted_desc}\n\n"
                f"**Recommended Level**: {encounter_channel.recommended_level}\n"
                f"**Table**: {encounter_channel.enc_table_name} (`/enc <tier>`)\n"
                f"**Onward Travel**: {encounter_channel.onward_travel}"
            ),
            embed=embed,
        )
    except disnake.NotFound:
        if recreate_if_missing:
            new_message = await _send_encchannel_message(channel, encounter_channel)
            encounter_channel.pinned_message_id = new_message.id
