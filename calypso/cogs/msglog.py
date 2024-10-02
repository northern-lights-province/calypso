import json

import disnake
from disnake.ext import commands

from calypso import db, models


class MessageLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.is_system():
            return

        guild_id = message.guild.id if message.guild else None
        clean_content = message.clean_content
        embeds_json = json.dumps([e.to_dict() for e in message.embeds]) if message.embeds else None

        thread_kwargs = {}
        if isinstance(message.channel, disnake.Thread):
            thread_kwargs["parent_id"] = message.channel.parent_id
            thread_kwargs["parent_name"] = message.channel.parent.name

        # record user msg in db
        async with db.async_session() as session:
            user_msg = models.LoggedMessage(
                # ids
                message_id=message.id,
                channel_id=message.channel.id,
                guild_id=guild_id,
                author_id=message.author.id,
                # names
                channel_name=str(message.channel),
                author_display_name=message.author.display_name,
                # content
                content=message.content,
                clean_content=clean_content,
                embeds_json=embeds_json,
                # thread info
                **thread_kwargs,
            )
            session.add(user_msg)
            await session.commit()


def setup(bot):
    bot.add_cog(MessageLog(bot))
