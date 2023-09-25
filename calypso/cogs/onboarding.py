import disnake
from disnake.ext import commands

from calypso import constants, utils

ONBOARDING_BUTTON_ID = "onboarding.agree"
THREAD_BUTTON_ID = "onboarding.thread"


class Onboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # SETUP
    @commands.slash_command(description="Sends a new button to accept the rules, in this channel.", dm_permission=False)
    @commands.default_member_permissions(manage_guild=True)
    async def send_onboarding_button(
        self,
        inter: disnake.MessageCommandInteraction,
        label: commands.String[1, 80] = None,
        emoji: str = None,
        style: disnake.ButtonStyle = disnake.ButtonStyle.primary.value,
    ):
        if label is None:
            label = "I agree"
        if emoji is not None:
            emoji = disnake.PartialEmoji.from_str(emoji)
        await inter.channel.send(
            components=disnake.ui.Button(
                style=disnake.ButtonStyle(style), emoji=emoji, label=label, custom_id=ONBOARDING_BUTTON_ID
            )
        )
        await inter.send("ok", ephemeral=True)

    async def on_onboard_click(self, interaction: disnake.MessageInteraction):
        member: disnake.Member = interaction.author
        if member.get_role(constants.MEMBER_ROLE_ID) is not None:
            return await interaction.send("You have already agreed to the rules.", ephemeral=True)
        # user is new, add the member role and welcome them in general
        await interaction.send(
            "Welcome to the Northern Lights Province!\nYou now have access to the rest of the server. Come say"
            f" hello in <#{constants.GENERAL_CHANNEL_ID}> and take a look at our resources channels (just below"
            " this channel) to get started!",
            ephemeral=True,
        )
        await member.add_roles(interaction.guild.get_role(constants.MEMBER_ROLE_ID), reason="Accepted rules")
        await interaction.guild.get_channel(constants.GENERAL_CHANNEL_ID).send(
            f"Welcome to the Northern Lights Province, {member.mention}!"
        )

    # thread
    @commands.slash_command(
        description="Sends a new button to create a private thread, in this channel.", dm_permission=False
    )
    @commands.default_member_permissions(manage_guild=True)
    async def send_thread_button(
        self,
        inter: disnake.MessageCommandInteraction,
        label: commands.String[1, 80] = None,
        emoji: str = None,
        style: disnake.ButtonStyle = disnake.ButtonStyle.primary.value,
    ):
        if label is None:
            label = "Create thread"
        if emoji is not None:
            emoji = disnake.PartialEmoji.from_str(emoji)
        await inter.channel.send(
            components=disnake.ui.Button(
                style=disnake.ButtonStyle(style), emoji=emoji, label=label, custom_id=THREAD_BUTTON_ID
            )
        )
        await inter.send("ok", ephemeral=True)

    async def on_thread_click(self, interaction: disnake.MessageInteraction):
        thread_name = utils.smart_trim(f"Character Submission: {interaction.author.name}", max_len=80)
        channel = interaction.channel
        thread = await channel.create_thread(
            name=thread_name,
            type=disnake.ChannelType.private_thread,
            auto_archive_duration=1440,
        )
        await thread.add_user(interaction.author)

    # listener
    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        if interaction.guild_id != constants.GUILD_ID:
            return
        if not isinstance(interaction.author, disnake.Member):
            return
        if interaction.data.custom_id == ONBOARDING_BUTTON_ID:
            return await self.on_onboard_click(interaction)
        if interaction.data.custom_id == THREAD_BUTTON_ID:
            return await self.on_thread_click(interaction)


def setup(bot):
    bot.add_cog(Onboarding(bot))
