import base64
import collections
import io
import json
import logging
import re

import disnake
from disnake.ext import commands
from kani import ChatMessage, ChatRole
from kani.engines.anthropic import AnthropicUnknownPart
from kani.engines.anthropic.parts import AnthropicThinkingPart

from calypso import Calypso, config, constants, db, models
from calypso.utils.functions import send_chunked
from .aikani import AIKani
from .engines import CHAT_HYPERPARAMS, chat_engine
from .prompts import AI_CHAT_PROMPT, chat_prompt

log = logging.getLogger(__name__)


class AIUtils(commands.Cog):
    """Various AI utilities for players and DMs."""

    def __init__(self, bot):
        self.bot: Calypso = bot
        self.chats: dict[int, AIKani] = {}
        self.chat_input_buffer: dict[int, list[str]] = collections.defaultdict(list)

    @commands.slash_command(name="ai", description="AI utilities", guild_ids=[constants.GUILD_ID])
    async def ai(self, inter: disnake.ApplicationCommandInteraction):
        pass

    # ==== text2auto ====
    # @ai.sub_command_group(name="text2auto")
    # async def ai_text2auto(self, inter: disnake.ApplicationCommandInteraction):
    #     pass
    #
    # @ai_text2auto.sub_command(name="monster", description="Generate automation for a monster's ability (2 steps).")
    # async def ai_text2auto_monster(
    #     self,
    #     inter: disnake.ApplicationCommandInteraction,
    #     monster: str = commands.Param(desc="The name of the monster."),
    #     ability: str = commands.Param(desc="The name of the ability."),
    #     critterdb_format: bool = commands.Param(True, desc="Whether to return CritterDB override syntax."),
    # ):
    #     try:
    #         modal_inter, ability_text = await multiline_modal(
    #             inter, title=f"{monster}: {ability}", label="Paste the ability's full description", timeout=600
    #         )
    #     except asyncio.TimeoutError:
    #         return
    #     await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
    #     await modal_inter.channel.trigger_typing()
    #
    #     # build prompt and query GPT-3
    #     prompt = f"{monster}: {ability}\n{ability_text}\n###\n"
    #     completion = await self.bot.openai_kani.create_completion(
    #         model=constants.ABILITY_AUTOMATION_MODEL,
    #         prompt=prompt,
    #         temperature=0.1,
    #         max_tokens=1024,
    #         stop=["\n^^^"],
    #         top_p=0.95,
    #         user=str(inter.author.id),
    #     )
    #     automation = completion.text.strip()
    #     if automation == "meta: No automation":
    #         automation_chunks = ["No automation was generated. Perhaps this ability doesn't need automation."]
    #     elif critterdb_format:
    #         automation_chunks = chunk_text(
    #             f"<avrae hidden>\nname: {ability}\n_v: 2\nautomation:\n{automation}\n</avrae>",
    #             max_chunk_size=1900,
    #             chunk_on=("\n",),
    #         )
    #     else:
    #         automation_chunks = chunk_text(automation, max_chunk_size=1900, chunk_on=("\n",))
    #
    #     for chunk in automation_chunks:
    #         await modal_inter.channel.send(f"```yaml\n{chunk}\n```")

    # @ai_text2auto.sub_command(
    #     name="monster-32k", description="Generate automation for a monster's ability using GPT-4 32k."
    # )
    # async def ai_text2auto_monster_gpt4_32k(
    #     self,
    #     inter: disnake.ApplicationCommandInteraction,
    #     monster: str = commands.Param(desc="The name of the monster."),
    #     ability: str = commands.Param(desc="The name of the ability."),
    # ):
    #     try:
    #         modal_inter, ability_text = await multiline_modal(
    #             inter, title=f"{monster}: {ability}", label="Paste the ability's full description", timeout=600
    #         )
    #     except asyncio.TimeoutError:
    #         return
    #     await modal_inter.send(f"Generating Avrae automation for {monster}: {ability}```\n{ability_text}\n```")
    #     await modal_inter.channel.trigger_typing()
    #
    #     # build prompt and query GPT-4
    #     avrae_docs = (utils.REPO_ROOT / "data" / "automation_ref.rst").read_text()
    #     prompt = [
    #         ChatMessage.system("You are a D&D player writing game automation for new monsters."),
    #         ChatMessage.user(
    #             "Here is the documentation for the automation language, written in ReStructuredText format:\n"
    #             f"{avrae_docs}\n\n"
    #             "Please write automation in JSON format for the following ability. Your"
    #             " output should be an AttackModel.\n\n"
    #             f"{monster}: {ability}. {ability_text}"
    #         ),
    #     ]
    #     completion = await self.bot.openai_kani.create_chat_completion(
    #         model="gpt-4-32k",
    #         messages=prompt,
    #         temperature=0.1,
    #         max_tokens=1024,
    #         top_p=0.95,
    #         user=str(inter.author.id),
    #     )
    #
    #     # just print its response
    #     automation_chunks = chunk_text(
    #         completion.message.text,
    #         max_chunk_size=1900,
    #         chunk_on=("\n",),
    #     )
    #     for chunk in automation_chunks:
    #         await modal_inter.channel.send(chunk)

    # === chatgpt ===
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.channel.id not in self.chats:
            return
        if message.author.bot or message.is_system():
            return
        if message.content.startswith("!"):
            return

        # create the prompt and add it to the channel buffer
        chatter = self.chats[message.channel.id]
        chatter.last_user_message_id = message.id
        prompt = chat_prompt(message)
        self.chat_input_buffer[message.channel.id].append(prompt)

        async with db.async_session() as session:
            # if the lock is held, terminate here; otherwise enter the buffer consumption loop
            if chatter.lock.locked():
                return

            # consume all messages from the input buffer until we have none left (future discord messages might add to
            # the buf before we are done processing one)
            async with message.channel.typing():
                while buf := self.chat_input_buffer[message.channel.id]:
                    prompt = "\n\n---\n\n".join(buf)
                    buf.clear()

                    user_msg = models.AIChatMessageRaw(
                        chat_id=chatter.chat_session_id, data=ChatMessage.user(prompt).model_dump_json(fallback=repr)
                    )
                    session.add(user_msg)
                    await session.commit()

                    try:
                        async for stream in chatter.full_round_stream(
                            prompt, cache_control={"type": "ephemeral"}, max_function_rounds=32
                        ):
                            msg = await stream.message()
                            log.debug(msg)
                            if msg.role == ChatRole.ASSISTANT:
                                await send_ai_msg(message.channel, msg)

                            # record msg in db
                            model_msg = models.AIChatMessageRaw(
                                chat_id=chatter.chat_session_id, data=msg.model_dump_json(fallback=repr)
                            )
                            session.add(model_msg)
                            await session.commit()
                    except Exception as e:
                        log.warning("Failed to generate AI chat message", exc_info=e)
                        await message.channel.send(f"-# > Calypso failed with error: {e}")

    @commands.Cog.listener()
    async def on_thread_update(self, _, after: disnake.Thread):
        if after.archived and after.id in self.chats:
            del self.chats[after.id]

    @ai.sub_command(name="chat", description="Chat with Calypso (experimental).")
    async def ai_chat(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ):
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
            engine=chat_engine,
            system_prompt=AI_CHAT_PROMPT,
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

    # ==== dalle ====
    # @commands.slash_command(
    #     name="dalle",
    #     description="Generate an image from a description.",
    #     guild_ids=[constants.GUILD_ID],
    #     dm_permission=True,
    # )
    # async def dalle(
    #     self,
    #     inter: disnake.ApplicationCommandInteraction,
    #     prompt: str = commands.Param(desc="The image description."),
    #     aspect_ratio: str = commands.Param("square", choices=["square", "portrait", "landscape"]),
    #     style: str = commands.Param("vivid", choices=["vivid", "natural"]),
    # ):
    #     await inter.response.defer()
    #
    #     if aspect_ratio == "portrait":
    #         size = "1024x1792"
    #     elif aspect_ratio == "landscape":
    #         size = "1792x1024"
    #     else:
    #         size = "1024x1024"
    #
    #     # generate image and parse webp + metadata
    #     resp = await self.bot.openai.images.generate(
    #         prompt=prompt,
    #         model="dall-e-3",
    #         n=1,
    #         quality="hd",
    #         response_format="b64_json",
    #         size=size,
    #         style=style,
    #         user=str(inter.author.id),
    #         extra_headers={"OpenAI-Organization": config.DALLE_ORG_ID} if config.DALLE_ORG_ID else None,
    #     )
    #     image = resp.data[0]
    #     data_bytes = base64.b64decode(image.b64_json)
    #     data = io.BytesIO(data_bytes)
    #     prompt_filename = re.sub(r"[^\w\d\-_]", "-", f"{inter.author.name}-{prompt}"[:64]) + ".webp"
    #
    #     # save to db
    #     async with db.async_session() as session:
    #         db_img = models.DalleImage(
    #             author_id=inter.author.id,
    #             model="dall-e-3",
    #             prompt=prompt,
    #             size=size,
    #             style=style,
    #             data=data_bytes,
    #             filename=prompt_filename,
    #             revised_prompt=image.revised_prompt,
    #         )
    #         session.add(db_img)
    #         await session.commit()
    #
    #     # send
    #     out = f"**Prompt**: {prompt[:800]}"
    #     if image.revised_prompt:
    #         out += f"\n\n**Interpreted as**: {image.revised_prompt[:800]}"
    #     await inter.send(out, file=disnake.File(data, prompt_filename))

    @commands.slash_command(
        name="gptimage",
        description="Generate an image from a description using the new GPT image model.",
        guild_ids=[constants.GUILD_ID],
        dm_permission=True,
    )
    async def gptimage(
        self,
        inter: disnake.ApplicationCommandInteraction,
        prompt: str = commands.Param(desc="The image description."),
        quality: str = commands.Param("medium", choices=["high", "medium", "low"]),
        aspect_ratio: str = commands.Param("auto", choices=["auto", "square", "portrait", "landscape"]),
    ):
        await inter.response.defer()

        if aspect_ratio == "portrait":
            size = "1024x1536"
        elif aspect_ratio == "landscape":
            size = "1536x1024"
        elif aspect_ratio == "square":
            size = "1024x1024"
        else:
            size = "auto"

        # generate image and parse webp + metadata
        resp = await self.bot.openai.images.generate(
            prompt=prompt,
            model="gpt-image-2",
            moderation="low",
            n=1,
            quality=quality,
            output_format="webp",
            size=size,
            user=str(inter.author.id),
            extra_headers={"OpenAI-Organization": config.DALLE_ORG_ID} if config.DALLE_ORG_ID else None,
        )
        image = resp.data[0]
        data_bytes = base64.b64decode(image.b64_json)
        data = io.BytesIO(data_bytes)
        prompt_filename = re.sub(r"[^\w\d\-_]", "-", f"{inter.author.name}-{prompt}"[:64]) + ".webp"

        # send
        out = f"**Prompt**: {prompt[:800]}"
        await inter.send(out, file=disnake.File(data, prompt_filename))

        # save to db
        async with db.async_session() as session:
            db_img = models.DalleImage(
                author_id=inter.author.id,
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                style="N/A",
                data=data_bytes,
                filename=prompt_filename,
                revised_prompt="N/A",
            )
            session.add(db_img)
            await session.commit()


async def send_ai_msg(dest, msg):
    thinking_buf = []
    content_buf = []
    tool_buf = []
    for part in msg.parts:
        match part:
            case AnthropicUnknownPart(type="server_tool_use", data={"name": "web_search", "input": {"query": q}}):
                tool_buf.append(f"> -# Calypso searched for: `{q}`")
            case AnthropicUnknownPart(type="web_fetch_tool_result", data={"content": {"url": url}}):
                tool_buf.append(f"> -# Calypso visited: `{url}`")
            case AnthropicThinkingPart(content=str(thinking)) if thinking:
                thinking_clean = thinking.replace("\n", " ").replace("||", "|")
                thinking_buf.append(f"> -# Thinking: ||{thinking_clean}||")
            case _:
                content_buf.append(str(part))

    if msg.tool_calls:
        tool_calls = ", ".join(f"`{tc.function.name}`" for tc in msg.tool_calls)
        tool_calls_str = f"\n> -# Calypso used tools: {tool_calls}"
        tool_buf.append(tool_calls_str)

    # render
    if thinking_buf:
        # special case: if only thinking + tool, send them in the same message
        if not content_buf:
            thinking_buf.extend(tool_buf)
            tool_buf.clear()
        await send_chunked(dest, "\n".join(thinking_buf), allowed_mentions=disnake.AllowedMentions.none())

    # otherwise send content (plus possible tools) in own message
    if content_buf or tool_buf:
        out = "".join(content_buf) + "\n" + "\n".join(tool_buf)
        await send_chunked(dest, out.strip(), allowed_mentions=disnake.AllowedMentions.none())
