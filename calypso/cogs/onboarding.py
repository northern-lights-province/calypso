import disnake
from disnake.ext import commands

from calypso import constants

ONBOARDING_BUTTON_ID = "onboarding.agree"


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

    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        if interaction.guild_id != constants.GUILD_ID:
            return
        if interaction.data.custom_id != ONBOARDING_BUTTON_ID:
            return
        if not isinstance(interaction.author, disnake.Member):
            return
        member: disnake.Member = interaction.author
        if member.get_role(constants.MEMBER_ROLE_ID) is not None:
            return await interaction.send("You have already agreed to the rules.", ephemeral=True)
        # user is new, add the member role and welcome them in general
        await interaction.send(
            "Welcome to the Northern Lights Province!\nYou now have access to the rest of the server. Come say hello"
            f" in <#{constants.GENERAL_CHANNEL_ID}> and take a look at our resources channels (just below this channel)"
            " to get started!",
            ephemeral=True,
        )
        await member.add_roles(interaction.guild.get_role(constants.MEMBER_ROLE_ID), reason="Accepted rules")
        await interaction.guild.get_channel(constants.GENERAL_CHANNEL_ID).send(
            f"Welcome to the Northern Lights Province, {member.mention}!"
        )


def setup(bot):
    bot.add_cog(Onboarding(bot))
