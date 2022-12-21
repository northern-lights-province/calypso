from .cog import CommunityGoals


def setup(bot):
    cgoals = CommunityGoals(bot)
    bot.add_cog(cgoals)
