import datetime
import logging

import disnake
from disnake.ext import commands

from calypso import Calypso, constants, db, models
from . import constants as xp_constants, queries, utils


class XPTracking(commands.Cog):
    """Experience tracking."""

    def __init__(self, bot):
        self.bot: Calypso = bot

    # ==== core event listener ====
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot or message.is_system():
            return
        guild = message.guild
        if guild is None:
            return
        author_id = message.author.id
        if message.content.startswith(xp_constants.IGNORE_PREFIX):
            return
        if len(message.content) < xp_constants.MIN_MESSAGE_LEN:
            return

        # add the XP and commit
        async with db.async_session() as session:
            player_xp = await queries.get_player_xp(session, guild.id, author_id)
            if isinstance(message.channel, disnake.Thread):
                channel_config = await queries.get_channel_config_from_hierarchy(
                    session,
                    guild_id=guild.id,
                    category_id=message.channel.category_id,
                    channel_id=message.channel.parent_id,
                    thread_id=message.channel.id,
                )
            else:
                channel_config = await queries.get_channel_config_from_hierarchy(
                    session,
                    guild_id=guild.id,
                    category_id=message.channel.category_id,
                    channel_id=message.channel.id,
                    thread_id=None,
                )
            if channel_config.xp_multiplier <= 0.0:
                return
            xp_to_award = int(channel_config.xp_multiplier * xp_constants.XP_PER_MESSAGE)
            if player_xp is None:
                player_xp = models.XPPlayer(guild_id=guild.id, member_id=author_id, xp=xp_to_award)
                old_xp = 0
                session.add(player_xp)
            else:
                # if the player most recently got XP too recently, abort
                now = message.created_at.replace(tzinfo=None)
                if player_xp.last_awarded_xp >= now - datetime.timedelta(seconds=xp_constants.XP_COOLDOWN_SECS):
                    return
                old_xp = player_xp.xp
                player_xp.xp += xp_to_award
                player_xp.last_awarded_xp = now
            print(f"xp awarded to {message.author}")
            await session.commit()
        await self._process_xp_transitions(guild.id, message.author.id, old_xp, player_xp.xp)

    async def _process_xp_transitions(self, guild_id: int, member_id: int, old_xp: int, new_xp: int):
        if guild_id != constants.GUILD_ID:  # technically this has multiguild support, but only do anything in NLP
            return

        # get rich objects
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(member_id)
        level_up_channel = self.bot.get_channel(xp_constants.LEVEL_UP_CHANNEL)
        if guild is None or member is None or level_up_channel is None:
            return

        # if the new xp is a different level,
        old_level = utils.level_from_xp(old_xp)
        new_level = utils.level_from_xp(new_xp)
        if old_level == new_level:
            return

        # send a level up message
        await level_up_channel.send(
            xp_constants.LEVEL_UP_TEMPLATE.format(member_mention=member.mention, new_level=new_level),
            allowed_mentions=disnake.AllowedMentions(users=[member]),
        )

        # and ensure roles
        role_ids = set(r.id for r in member.roles)
        for level_threshold, role_id in xp_constants.ROLE_THRESHOLDS:
            if new_level >= level_threshold:
                role_ids.add(role_id)
            else:
                role_ids.discard(role_id)
        new_roles = [guild.get_role(r) for r in role_ids]
        if any(r is None for r in new_roles):
            logging.warning(f"Could not find one or more roles in {guild_id=}: {role_ids=}")
            return
        await member.edit(roles=new_roles)

    # ==== player commands ====
    @commands.slash_command(name="xp", description="XP-related commands.")
    @commands.contexts(guild=True, bot_dm=False, private_channel=False)
    async def xp(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @xp.sub_command(name="view", description="View your XP.")
    async def xp_view(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: disnake.Member | None = commands.Param(
            default=None, desc="The member to view XP for (defaults to yourself)."
        ),
    ):
        guild = inter.guild
        if guild is None or inter.guild_id is None:  # technically redundant but helps the type checker
            await inter.send("This command can only be used in guilds.")
            return
        if target is None:
            target = inter.author
        target_id = target.id
        async with db.async_session() as session:
            player_xp = await queries.get_player_xp(session, guild.id, target_id)
            if player_xp is None:
                await inter.send("This member does not have any tracked XP.")
                return
            xp = player_xp.xp

        embed = disnake.Embed(title=f"Level and XP for {target.display_name}", colour=disnake.Colour.random())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon is not None else None)

        embed.add_field(name="Total XP", value=str(xp))
        embed.add_field(name="Level", value=str(utils.level_from_xp(xp)))
        embed.add_field(name="Progress", value=utils.progress_to_next_level(xp))
        await inter.send(embed=embed)

    # ==== admin config commands ====
    @commands.slash_command(name="xpadmin", description="Manage XP settings")
    @commands.default_member_permissions(manage_guild=True)
    @commands.contexts(guild=True, bot_dm=False, private_channel=False)
    async def xpadmin(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @xpadmin.sub_command(name="channel-list", description="View all configured XP rates.")
    async def xpadmin_channel_list(self, inter: disnake.ApplicationCommandInteraction):
        guild = inter.guild
        if guild is None or inter.guild_id is None:  # technically redundant but helps the type checker
            await inter.send("This command can only be used in guilds.")
            return

        async with db.async_session() as session:
            configs = await queries.get_channel_configs(session, inter.guild_id)
            configs_by_id = {cfg.channel_id: cfg for cfg in configs}

        if not configs:
            await inter.send("You have not configured any channels in this guild. All channels will award XP.")
            return

        out_embed = disnake.Embed(title=f"XP Configuration for {guild.name}", color=disnake.Colour.random())
        for category, channels in guild.by_category():
            category_name = "No Category" if category is None else category.name
            overrides_desc = []
            if category is not None and category.id in configs_by_id:
                cfg = configs_by_id[category.id]
                overrides_desc.append(f"*Whole category: {cfg.xp_multiplier:.2f}x*")

            for chan in channels:
                if chan.id not in configs_by_id:
                    continue
                cfg = configs_by_id[chan.id]
                overrides_desc.append(f"{chan.mention} - {cfg.xp_multiplier:.2f}x")

                if hasattr(chan, "threads"):
                    for thread in chan.threads:
                        if thread.id not in configs_by_id:
                            continue
                        cfg = configs_by_id[chan.id]
                        overrides_desc.append(f"    {chan.mention} - {cfg.xp_multiplier:.2f}x")

            channel_overrides = "\n".join(overrides_desc) if overrides_desc else "No overrides set."
            out_embed.add_field(name=category_name, value=channel_overrides)
        await inter.send(embed=out_embed)

    @xpadmin.sub_command(name="channel-config", description="Set XP rates for a channel.")
    async def xpadmin_channel_config(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.abc.GuildChannel = commands.Param(
            desc="The channel or category to configure. Specific overrides general."
        ),
        multiplier: float = commands.Param(desc="XP multiplier for this channel."),
    ):
        if not inter.guild_id:
            await inter.send("This command can only be used in guilds.")
            return
        async with db.async_session() as session:
            existing = await queries.get_channel_config(session, channel.id)
            if existing:
                existing.xp_multiplier = multiplier
            else:
                new_config = models.XPChannelConfig(
                    guild_id=inter.guild_id, channel_id=channel.id, xp_multiplier=multiplier
                )
                session.add(new_config)
            await session.commit()
        await inter.send(f"Updated {channel.mention} XP multiplier to **{multiplier}**.")

    @xpadmin.sub_command(name="set-xp", description="Set the XP for a given player or role.")
    async def xpadmin_set_xp(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: disnake.Member | disnake.Role = commands.Param(
            desc="The target to set the XP of. Selecting a role sets XP for all members of that role."
        ),
        amount: int = commands.Param(desc="XP amount to set the target to."),
    ):
        await inter.response.defer()
        guild = inter.guild
        if not guild:
            await inter.send("This command can only be used in guilds.")
            return
        if isinstance(target, disnake.Member):
            targets = [target.id]
        elif isinstance(target, disnake.Role):
            targets = [m.id for m in target.members if not m.bot]
        else:
            await inter.send(f"I don't know how to set the XP for {target}. Please select a member or role.")
            return

        transitions = []
        async with db.async_session() as session:
            for target_id in targets:
                player_xp = await queries.get_player_xp(session, guild.id, target_id)
                if player_xp is None:
                    player_old_xp = 0
                    player_xp = models.XPPlayer(guild_id=guild.id, member_id=target_id, xp=amount)
                    session.add(player_xp)
                else:
                    player_old_xp = player_xp.xp
                    player_xp.xp = amount
                transitions.append((target_id, player_old_xp, amount))
            await session.commit()
        for target_id, old_xp, new_xp in transitions:
            await self._process_xp_transitions(guild.id, target_id, old_xp, new_xp)
        await inter.send(f"Set {len(targets)} XP rows to **{amount}**.")

    @xpadmin.sub_command(name="add-xp", description="Add XP for a given player or role.")
    async def xpadmin_add_xp(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: disnake.Member | disnake.Role = commands.Param(
            desc="The target to set the XP of. Selecting a role sets XP for all members of that role."
        ),
        amount: int = commands.Param(desc="XP amount to award."),
    ):
        await inter.response.defer()
        guild = inter.guild
        if not guild:
            await inter.send("This command can only be used in guilds.")
            return
        if isinstance(target, disnake.Member):
            targets = [target.id]
        elif isinstance(target, disnake.Role):
            targets = [m.id for m in target.members if not m.bot]
        else:
            await inter.send(f"I don't know how to set the XP for {target}. Please select a member or role.")
            return

        transitions = []
        async with db.async_session() as session:
            for target_id in targets:
                player_xp = await queries.get_player_xp(session, guild.id, target_id)
                if player_xp is None:
                    player_old_xp = 0
                    player_xp = models.XPPlayer(guild_id=guild.id, member_id=target_id, xp=amount)
                    session.add(player_xp)
                else:
                    player_old_xp = player_xp.xp
                    player_xp.xp += amount
                transitions.append((target_id, player_old_xp, player_xp.xp))
            await session.commit()
        for target_id, old_xp, new_xp in transitions:
            await self._process_xp_transitions(guild.id, target_id, old_xp, new_xp)
        await inter.send(f"Added **{amount}** XP to {len(targets)} XP rows.")
