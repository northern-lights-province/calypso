from typing import TYPE_CHECKING

from kani import ChatMessage, ChatRole, Kani, ai_function

if TYPE_CHECKING:
    from calypso import Calypso


class AIKani(Kani):
    def __init__(self, *args, bot: "Calypso", channel_id: int, chat_session_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.channel_id = channel_id
        self.chat_session_id = chat_session_id
        self.chat_title = None

    @property
    def last_user_message(self) -> ChatMessage | None:
        return next((m for m in self.chat_history if m.role == ChatRole.USER), None)

    # ==== discord ====
    @ai_function()
    async def react(self, emoji: str):
        """Add an emoji reaction to the last message if it was particularly funny or evoking.

        The reaction can be a unicode emoji, or one of the following literal strings:
        `<:NekoHeadpat:1031982950499221555>`
        `<:NekoRage:1032002382441226321>`
        `<:NekoFlop:1032002522589692084>`
        `<:NekoWave:1032002556802650223>`
        `<:NekoBonk:1031982834581241866>`
        `<:NekoPeek:1031982986738020434>`
        `<:blobknife:1132579989427060746>`
        `<:BlobhajHeart:1034241839554908260>`
        """
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        message = channel.last_message
        if message is None:
            message = await channel.history(limit=1).next()
        await message.add_reaction(emoji)
        return "Added a reaction."
