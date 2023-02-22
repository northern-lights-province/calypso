import datetime
import logging
import traceback
from math import floor, isfinite

import disnake
from disnake.ext import commands

from calypso import config, db, errors

COGS = (
    "calypso.cogs.weather",
    "calypso.cogs.admin",
    "calypso.cogs.onboarding",
    "calypso.cogs.encounters",
    "calypso.cogs.cgoals",
    "calypso.cogs.ai",
    "calypso.cogs.utils",
)

logging.basicConfig(level=logging.INFO)


class Calypso(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


intents = disnake.Intents.all()
bot = Calypso(
    command_prefix=commands.when_mentioned,
    intents=intents,
    sync_commands_debug=True,
)


# === listeners ===
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.event
async def on_slash_command_error(inter, error):
    if isinstance(error, commands.CommandInvokeError):
        error = error.original

    await inter.send(f"Error: {error!s}", ephemeral=True)

    if not isinstance(error, errors.CalypsoError):
        traceback.print_exception(error)


# === commands ===
@bot.slash_command()
async def ping(inter: disnake.ApplicationCommandInteraction):
    """Returns the bot's latency to the Discord API."""
    now = datetime.datetime.utcnow()
    await inter.response.defer()  # this makes an API call, we use the RTT of that call as the latency
    delta = datetime.datetime.utcnow() - now
    httping = floor(delta.total_seconds() * 1000)
    wsping = floor(bot.latency * 1000) if isfinite(bot.latency) else "Unknown"
    await inter.followup.send(f"Pong.\nHTTP Ping = {httping} ms.\nWS Ping = {wsping} ms.")


for cog in COGS:
    bot.load_extension(cog)

if __name__ == "__main__":
    bot.loop.create_task(db.init_db())
    bot.run(config.TOKEN)
