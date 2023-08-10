from .cog import AIUtils


def setup(bot):
    ai_cog = AIUtils(bot)
    bot.add_cog(ai_cog)
