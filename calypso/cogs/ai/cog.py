import asyncio
import json

import disnake
from disnake.ext import commands
from kani import ChatMessage, ChatRole
from playwright.async_api import async_playwright

from calypso import Calypso, constants, db, models, utils
from calypso.utils.functions import chunk_text, multiline_modal, send_chunked
from calypso.utils.prompts import chat_prompt
from .aikani import AIKani
from .engines import CHAT_HYPERPARAMS, chat_engine


class AIUtils(commands.Cog):
    """Various AI utilities for players and DMs."""

    def __init__(self, bot):
        self.bot: Calypso = bot
        self.chats: dict[int, AIKani] = {}
        self.playwright = None
        self.browser = None

    async def cog_load(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    @commands.slash_command(name="ai", description="AI utilities", guild_ids=[constants.GUILD_ID])
    async def ai(self, inter: disnake.ApplicationCommandInteraction):
        pass

    # ==== text2auto ====
    @ai.sub_command_group(name="text2auto")
    async def ai_text2auto(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ai_text2auto.sub_command(name="monster", description="Generate automation for a monster's ability (2 steps).")
    async def ai_text2auto_monster(
        self,
        inter: disnake.ApplicationCommandInteraction,
        monster: str = commands.Param(desc="The name of the monster."),
        ability: str = commands.Param(desc="The name of the ability."),
        critterdb_format: bool = commands.Param(True, desc="Whether to return CritterDB override syntax."),
    ):
        try:
            modal_inter, ability_text = await multiline_modal(
                inter, title=f"{monster}: {ability}", label="Paste the ability's full description", timeout=600
            )
        except asyncio.TimeoutError:
            return
        await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
        await modal_inter.channel.trigger_typing()

        # build prompt and query GPT-3
        prompt = f"{monster}: {ability}\n{ability_text}\n###\n"
        completion = await self.bot.openai.create_completion(
            model=constants.ABILITY_AUTOMATION_MODEL,
            prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
            stop=["\n^^^"],
            top_p=0.95,
            user=str(inter.author.id),
        )
        automation = completion.text.strip()
        if automation == "meta: No automation":
            automation_chunks = ["No automation was generated. Perhaps this ability doesn't need automation."]
        elif critterdb_format:
            automation_chunks = chunk_text(
                f"<avrae hidden>\nname: {ability}\n_v: 2\nautomation:\n{automation}\n</avrae>",
                max_chunk_size=1900,
                chunk_on=("\n",),
            )
        else:
            automation_chunks = chunk_text(automation, max_chunk_size=1900, chunk_on=("\n",))

        for chunk in automation_chunks:
            await modal_inter.channel.send(f"```yaml\n{chunk}\n```")

    @ai_text2auto.sub_command(
        name="monster-32k", description="Generate automation for a monster's ability using GPT-4 32k."
    )
    async def ai_text2auto_monster_gpt4_32k(
        self,
        inter: disnake.ApplicationCommandInteraction,
        monster: str = commands.Param(desc="The name of the monster."),
        ability: str = commands.Param(desc="The name of the ability."),
    ):
        try:
            modal_inter, ability_text = await multiline_modal(
                inter, title=f"{monster}: {ability}", label="Paste the ability's full description", timeout=600
            )
        except asyncio.TimeoutError:
            return
        await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
        await modal_inter.channel.trigger_typing()

        # build prompt and query GPT-4
        avrae_docs = (utils.REPO_ROOT / "data" / "automation_ref.rst").read_text()
        prompt = [
            ChatMessage.system("You are a D&D player writing game automation for new monsters."),
            ChatMessage.user(
                "Here is the documentation for the automation language, written in ReStructuredText format:\n"
                f"{avrae_docs}\n\n"
                "Please write automation in JSON format for the following ability. Your"
                " output should be an AttackModel.\n\n"
                f"{monster}: {ability}. {ability_text}"
            ),
        ]
        completion = await self.bot.openai.create_chat_completion(
            model="gpt-4-32k",
            messages=prompt,
            temperature=0.1,
            max_tokens=1024,
            top_p=0.95,
            user=str(inter.author.id),
        )

        # just print its response
        automation_chunks = chunk_text(
            completion.text,
            max_chunk_size=1900,
            chunk_on=("\n",),
        )
        for chunk in automation_chunks:
            await modal_inter.channel.send(chunk)

    # === chatgpt ===
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.channel.id not in self.chats:
            return
        if message.author.bot or message.is_system():
            return

        # do a chat round w/ the chatterbox
        chatter = self.chats[message.channel.id]
        prompt = chat_prompt(message)

        # record user msg in db
        async with db.async_session() as session:
            user_msg = models.AIChatMessage(chat_id=chatter.chat_session_id, role=ChatRole.USER, content=prompt)
            session.add(user_msg)
            await session.commit()

            # do a chat round w/ the chatterbox
            async with message.channel.typing():
                async for msg in chatter.full_round(prompt, user=str(message.author.id)):
                    if msg.role == ChatRole.ASSISTANT and msg.content:
                        await send_chunked(
                            message.channel, msg.content, allowed_mentions=disnake.AllowedMentions.none()
                        )

                    # record msg in db
                    model_msg = models.AIChatMessage(
                        chat_id=chatter.chat_session_id, role=msg.role, content=msg.content
                    )
                    session.add(model_msg)
                    if msg.function_call:
                        func_call = models.AIFunctionCall(
                            message=model_msg, name=msg.function_call.name, arguments=msg.function_call.arguments
                        )
                        session.add(func_call)
                    await session.commit()

        # do a thread rename after 2 rounds
        if (
            chatter.chat_title is None
            and len(chatter.chat_history) >= 4
            and isinstance(message.channel, disnake.Thread)
        ):
            completion = await self.bot.openai.create_chat_completion(
                "gpt-4",
                [
                    ChatMessage.user("Here is the start of a conversation:"),
                    *chatter.chat_history,
                    ChatMessage.user(
                        "Come up with a punchy title for this conversation.\n\nReply with your answer only and be"
                        " specific."
                    ),
                ],
                user=str(message.author.id),
            )
            thread_title = completion.text.strip(' "')
            async with db.async_session() as session:
                db_chat = await session.get(models.AIOpenEndedChat, chatter.chat_session_id)
                chatter.chat_title = thread_title
                db_chat.thread_title = thread_title
                await session.commit()
            await message.channel.edit(name=thread_title)

    @commands.Cog.listener()
    async def on_thread_update(self, _, after: disnake.Thread):
        if after.archived and after.id in self.chats:
            del self.chats[after.id]

    @ai.sub_command(name="chat", description="Chat with Calypso (experimental).")
    async def ai_chat(self, inter: disnake.ApplicationCommandInteraction):
        # can only chat in OOC/staff category or ooc channel
        if not isinstance(inter.channel, disnake.TextChannel) and (
            inter.channel.category_id in (1031055347818971196, 1031651537543499827) or "ooc" in inter.channel.name
        ):
            await inter.send("Chatting with Calypso is not allowed in this channel.")
            return
        await inter.response.defer()

        # create thread, init chatter
        await inter.send("Making a thread now!")
        thread = await inter.channel.create_thread(
            name="Chat with Calypso", type=disnake.ChannelType.public_thread, auto_archive_duration=1440
        )
        chatter = AIKani(
            bot=self.bot,
            channel_id=thread.id,
            browser=self.browser,
            engine=chat_engine,
            system_prompt=(
                "You are a knowledgeable D&D player. Answer as concisely as possible.\nYou are acting as Calypso, a"
                " faerie from the Feywild. The user has already been introduced to you.\nEach reply should consist of"
                " just Calypso's response, without quotation marks.\nYou should stay in character no matter what the"
                " user says."
            ),
        )

        # register session in db
        async with db.async_session() as session:
            brainstorm = models.AIOpenEndedChat(
                channel_id=inter.channel_id,
                author_id=inter.author.id,
                prompt=json.dumps([m.model_dump(mode="json", exclude_none=True) for m in await chatter.get_prompt()]),
                hyperparams=json.dumps(CHAT_HYPERPARAMS),
                thread_id=thread.id,
            )
            session.add(brainstorm)
            await session.commit()
            chatter.chat_session_id = brainstorm.id

        # begin chat
        self.chats[thread.id] = chatter
        await thread.add_user(inter.author)
