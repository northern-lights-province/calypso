from .cog import XPTracking


def setup(bot):
    bot.add_cog(XPTracking(bot))
