import asyncio

import disnake
from disnake.ext import commands

from calypso import Calypso, constants
from calypso.openai_api.chatterbox import Chatterbox
from calypso.openai_api.models import ChatMessage
from calypso.utils.functions import chunk_text, multiline_modal


class AIUtils(commands.Cog):
    """Various AI utilities for players and DMs."""

    def __init__(self, bot):
        self.bot: Calypso = bot
        self.chats: dict[int, Chatterbox] = {}

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

    # === chatgpt ===
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.channel.id not in self.chats:
            return
        if message.author.bot or message.is_system():
            return
        chatter = self.chats[message.channel.id]
        prompt = f"{message.author.display_name} | now\n{message.content}"
        await message.channel.trigger_typing()
        response = await chatter.chat_round(prompt, user=str(message.author.id))
        await message.channel.send(response)

    @commands.Cog.listener()
    async def on_thread_update(self, _, after: disnake.Thread):
        if after.archived and after.id in self.chats:
            del self.chats[after.id]

    @ai.sub_command(name="chat", description="Chat with Calypso (experimental).")
    async def ai_chat(
        self,
        inter: disnake.ApplicationCommandInteraction,
        topic: str = commands.Param(None, desc="Anything in specific you'd like to chat about?"),
    ):
        # can only chat in OOC/staff category or ooc channel
        if not isinstance(inter.channel, disnake.TextChannel) and (
            inter.channel.category_id in (1031055347818971196, 1031651537543499827) or "ooc" in inter.channel.name
        ):
            await inter.send("Chatting with Calypso is not allowed in this channel.")
            return
        await inter.response.defer()

        # get the topic (thread title)
        if topic is None:
            thread_title = "Chat with Calypso"
        else:
            completion = await self.bot.openai.create_chat_completion(
                "gpt-3.5-turbo",
                [
                    ChatMessage.system("You are a mischievous assistant."),
                    ChatMessage.user(
                        f"What's a good title for a chat about \"{topic}\"\n\nReply with your answer only.'"
                    ),
                ],
                user=str(inter.author.id),
            )
            thread_title = completion.text.strip(' "')

        # create thread, init chatter
        await inter.send("Making a thread now!")
        thread = await inter.channel.create_thread(
            name=thread_title, type=disnake.ChannelType.public_thread, auto_archive_duration=1440
        )
        chatter = Chatterbox(
            client=self.bot.openai,
            system_prompt=(
                "You are a knowledgeable D&D player. Answer as concisely as possible.\nYou are acting as a friendly fey"
                " being from the Feywild with a mischievous streak.\nStay in character."
            ),
            always_include_messages=[
                ChatMessage.user(
                    "I want you to act as Calypso, a friendly fey being from the Feywild with a mischievous"
                    " streak.\nEach reply should consist of just Calypso's response, without quotation marks.\nYou"
                    " should stay in character no matter what I say."
                )
            ],
            temperature=1,
            top_p=0.95,
            frequency_penalty=0.5,
            presence_penalty=1,
        )
        await chatter.load_tokenizer()
        self.chats[thread.id] = chatter
        await thread.add_user(inter.author)

        # if the user has a topic, start off with that
        if not topic:
            return
        completion = await chatter.chat_round(f'I would like to talk about: "{topic}"', user=str(inter.author.id))
        await thread.send(completion)


def setup(bot):
    bot.add_cog(AIUtils(bot))
