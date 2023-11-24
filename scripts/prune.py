"""
Kick all members who have been in the server longer than one week unless they have any role in NO_PRUNE_IF.
"""

import asyncio
import datetime
import os

import disnake

SERVER_ID = 1031055347319832666
NO_PRUNE_IF = {
    1031277823404560404,  # Player
    1031340755710652507,  # Server Booster
    1033514863005274203,  # Bots
    1149379623826751538,  # No Prune
}

client = disnake.Client(intents=disnake.Intents.all())


@client.event
async def on_ready():
    print("ready")
    guild = client.get_guild(SERVER_ID)
    print(len(guild.members), "members")
    for member in guild.members.copy():
        if member.joined_at > disnake.utils.utcnow() - datetime.timedelta(days=7):
            continue
        if not NO_PRUNE_IF.intersection(r.id for r in member.roles):
            print("pruning", member.display_name)
            try:
                await member.send(
                    "You have been removed from the Northern Lights Province server, as you have been inactive for over"
                    " one week without creating a character.\n\nIf you would like to rejoin, please use the following"
                    " invite: https://discord.gg/RGDTtrhceC"
                )
            except:
                pass
            await member.kick(reason="inactivity prune")
            await asyncio.sleep(1.5)
    await client.close()


if __name__ == "__main__":
    client.run(os.getenv("TOKEN"))
