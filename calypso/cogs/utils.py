import disnake
from disnake.ext import commands


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.message_command(name="List Unique Reactors")
    async def reactors(self, inter: disnake.MessageCommandInteraction):
        await inter.response.defer(ephemeral=True)
        reacted_ids = {u.id for r in inter.target.reactions async for u in r.users()}
        reactor_mentions = "\n".join(f"<@{u}>" for u in reacted_ids)
        await inter.send(f"People who reacted to this message:\n{reactor_mentions}", ephemeral=True)


def setup(bot):
    bot.add_cog(Utils(bot))
