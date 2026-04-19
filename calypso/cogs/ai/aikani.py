from typing import TYPE_CHECKING

from kani import ChatMessage, ChatRole, Kani, ai_function

from calypso import db, models

if TYPE_CHECKING:
    from calypso import Calypso


class AIKani(Kani):
    def __init__(self, *args, bot: "Calypso", channel_id: int, chat_session_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.channel_id = channel_id
        self.chat_session_id = chat_session_id
        self.chat_title = None
        self.last_user_message_id = None

    @property
    def last_user_message(self) -> ChatMessage | None:
        return next((m for m in self.chat_history if m.role == ChatRole.USER), None)

    # ==== discord ====
    @ai_function()
    async def rename_thread(self, title: str):
        """
        Rename the thread that you are chatting with the user in.
        You should call this once when a topic has been established (usually after 2 or 3 rounds), and only on major changes to the conversation afterwards.
        The title should be short and objective; you do not need to follow your character persona for the title.
        """
        thread_title = title.strip(' "')
        async with db.async_session() as session:
            db_chat = await session.get(models.AIOpenEndedChat, self.chat_session_id)
            self.chat_title = thread_title
            db_chat.thread_title = thread_title
            await session.commit()
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        await channel.edit(name=thread_title)

    @ai_function()
    async def react(self, emoji: str):
        """
        Add an emoji reaction to the last user message if it was particularly funny or evoking.

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
        if self.last_user_message_id is None:
            return "The user has not sent any messages to react to."
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        message = channel.get_partial_message(self.last_user_message_id)
        await message.add_reaction(emoji)
        return "Added a reaction."
