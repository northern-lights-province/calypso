import datetime
import itertools
from typing import Annotated, Any, TYPE_CHECKING

import disnake
from disnake import ChannelType, Guild
from disnake.http import Route
from disnake.utils import snowflake_time, time_snowflake
from kani import AIParam, ChatMessage, ChatRole, Kani, ai_function

from calypso import constants, db, models
from .memory import (
    memory_create,
    memory_delete,
    memory_insert,
    memory_rename,
    memory_str_replace,
    memory_view,
)
from .prompts import chat_prompt

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

    # ==== meta ====
    @ai_function(enabled=False, json_schema={}, desc="managed by claude server")
    async def memory(self, command: str, **kwargs):
        # we use a disabled aifunction to handle claude server calls
        # https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#tool-commands
        match command, kwargs:
            # view
            case ("view", {"path": path, "view_range": (start, end)}):
                return await memory_view(path, start, end)
            case ("view", {"path": path}):
                return await memory_view(path)
            # create
            case ("create", {"path": path, "file_text": file_text}):
                return await memory_create(path, file_text)
            case ("create", {"path": path}):
                return await memory_create(path, "")
            # str_replace
            case ("str_replace", {"path": path, "old_str": old_str, "new_str": new_str}):
                return await memory_str_replace(path, old_str, new_str)
            # insert
            case ("insert", {"path": path, "insert_line": insert_line, "insert_text": insert_text}):
                return await memory_insert(path, insert_line, insert_text)
            # delete
            case ("delete", {"path": path}):
                return await memory_delete(path)
            # rename
            case ("rename", {"old_path": old_path, "new_path": new_path}):
                return await memory_rename(old_path, new_path)
            # default
            case _:
                raise ValueError("Unknown or malformed memory command")

    # ==== discord ====
    @ai_function()
    async def rename_thread(self, title: str):
        """
        Rename the thread that you are chatting with the user in.
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
        return f"Thread renamed to {thread_title!r}."

    @ai_function()
    async def react(self, emoji: str):
        """
        Add an emoji reaction to the last user message if it was particularly funny or evoking.

        The reaction can be any unicode emoji, or one of the following literal strings:
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

    @ai_function()
    async def list_channels(self):
        """
        List the publicly-visible channels in the Discord server.
        Returns the channel names, types, and IDs. Does not include threads; use list_threads(channel_id) to list threads.
        """
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        guild = channel.guild

        out = []
        for category, channels in guild.by_category():
            # filter to ones only players/members can see to prevent leeks
            visible_channels = [
                c
                for c in channels
                if is_public_to_roles(guild, [constants.MEMBER_ROLE_ID, constants.PLAYER_ROLE_ID], c)
            ]
            if not visible_channels:
                continue

            # list the channels
            channel_list = [f"{ch.name} ({ch.type.name}, ID: {ch.id})" for ch in visible_channels]
            if category:
                channel_list_indented = "\n".join(f"|- {c}" for c in channel_list)
                out.append(f"## {category.name}\n{channel_list_indented}")
            else:
                out.append("\n".join(channel_list))
        channel_list_str = "\n\n".join(out)
        return f"# Channels in {guild.name}\n\n{channel_list_str}"

    @ai_function()
    async def list_threads(
        self,
        channel_id: int,
        include_archived: bool = False,
        archived_before: Annotated[
            str, AIParam(desc="Retrieve archived threads sent before this timestamp or thread ID.")
        ] = None,
    ):
        """
        List the public threads in a given channel.
        Returns the thread names and IDs, and last message time.
        If `include_archived` is true, includes archived threads in batches of 50. Use `archived_before` to paginate. Always true for forum channels.
        """
        invoker_channel = await self.bot.get_or_fetch_channel(self.channel_id)
        target_channel = await self.bot.get_or_fetch_channel(channel_id)
        if not target_channel:
            raise ValueError("Target channel does not exist")
        if target_channel.guild != invoker_channel.guild:
            raise ValueError("Cannot list threads of a channel in a different guild")
        if not is_public_to_roles(
            target_channel.guild, [constants.MEMBER_ROLE_ID, constants.PLAYER_ROLE_ID], target_channel
        ):
            raise ValueError("Cannot list threads of a private channel")

        visible_threads = []
        for t in target_channel.threads:
            if not is_public_to_roles(invoker_channel.guild, [constants.MEMBER_ROLE_ID, constants.PLAYER_ROLE_ID], t):
                continue
            if t.is_private() or t.archived:
                continue
            visible_threads.append(t)
        # include archived threads for forums or if archived pagination set
        if target_channel.type == ChannelType.forum:
            async for t in target_channel.archived_threads(limit=None):
                visible_threads.append(t)
        elif include_archived:
            async for t in target_channel.archived_threads(before=archived_before):
                visible_threads.append(t)

        thread_list_str = "\n".join(
            f"{t.name} (ID: {t.id}, last message: {snowflake_time(t.last_message_id).strftime('%Y-%m-%d %H:%M:%S')})"
            for t in visible_threads
        )
        return f"# Threads in {target_channel.name}\n\n{thread_list_str}"

    @ai_function()
    async def list_members(self, name: str = None):
        """
        List the members in the Discord server (whose display names contain `name` if set).
        Returns the members' ID, username, display name, and relevant roles.
        """
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        members = channel.guild.members
        if name is not None:
            members = [m for m in members if name.lower() in m.display_name.lower()]
        member_list = []
        for m in members:
            relevant_role_list = [r for r in m.roles if r.id in (constants.STAFF_ROLE_ID, constants.DM_ROLE_ID)]
            relevant_roles = f", roles: {', '.join(r.name for r in relevant_role_list)}" if relevant_role_list else ""
            member_list.append(f"{m.display_name} (ID: {m.id}, username: {m.name}{relevant_roles})")
        member_list_str = "\n".join(member_list)
        return f"# Members in {channel.guild.name}\n\n{member_list_str}"

    @ai_function()
    async def get_channel_history(
        self,
        channel_id: int,
        n: Annotated[int, AIParam(desc="The number of messages to retrieve from the Discord channel.")] = 25,
        before: Annotated[str, AIParam(desc="Retrieve messages sent before this timestamp or message ID.")] = None,
        after: Annotated[str, AIParam(desc="Retrieve messages sent after this timestamp or message ID.")] = None,
    ):
        """
        View message history from a given channel or thread.
        Returns the message history with the most recent messages last.
        At most one of `before` or `after` should be set for search/pagination purposes.
        If `before` or `after` is a date, it should be formatted in `YYYY-MM-DD HH:mm:ss` format.
        """
        invoker_channel = await self.bot.get_or_fetch_channel(self.channel_id)
        target_channel = await self.bot.get_or_fetch_channel(channel_id)
        if not target_channel:
            raise ValueError("Target channel does not exist")
        if target_channel.guild != invoker_channel.guild:
            raise ValueError("Cannot view a channel in a different guild")
        if not is_public_to_roles(
            target_channel.guild, [constants.MEMBER_ROLE_ID, constants.PLAYER_ROLE_ID], target_channel
        ):
            raise ValueError("Cannot view a private channel")

        if before:
            before = ensure_datetime_or_id(before, "%Y-%m-%d %H:%M:%S")
        if after:
            after = ensure_datetime_or_id(after, "%Y-%m-%d %H:%M:%S")

        messages = await target_channel.history(limit=n, before=before, after=after).flatten()
        messages = sorted(messages, key=lambda m: m.id)
        return "\n\n".join(chat_prompt(m) for m in messages)

    @ai_function()
    async def search_discord(
        self,
        limit: int = 25,
        offset: int = None,
        before: str = None,
        after: str = None,
        content: str = None,
        channel_id: list[int] = None,
        author_id: list[int] = None,
        pinned: bool = None,
        link_hostname: list[str] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ):
        """
        Search the current Discord server for messages using a broad number of filters.

        **Query Params**
        Field	Type	Description
        limit?	integer	Max number of messages to return (1-25, default 25)
        offset?	integer	Number to offset the returned messages by (max 9975)
        before?	snowflake or datetime	Get messages before this message ID or `YYYY-MM-DD HH:mm:ss` format datetime
        after?	snowflake or datetime	Get messages after this message ID or `YYYY-MM-DD HH:mm:ss` format datetime
        content?	string	Filter messages by content (max 1024 characters)
        channel_id?	array of snowflakes	Filter messages by these channels (max 500)
        author_id?	array of snowflakes	Filter messages by these authors (max 100)
        pinned?	boolean	Filter messages by whether they are or are not pinned
        link_hostname?	array of strings	Filter messages by link hostname (e.g. discordapp.com) (max 256 characters, max 100)
        sort_by?	string	The sorting algorithm to use (timestamp or relevance, default timestamp)
        sort_order?	string	The direction to sort (asc or desc, default desc)
        """
        invoker_channel = await self.bot.get_or_fetch_channel(self.channel_id)
        guild = invoker_channel.guild
        # todo we do this manually since it's not in disnake yet
        r = Route("GET", "/guilds/{guild_id}/messages/search", guild_id=guild.id)
        params: dict[str, Any] = {"limit": limit}
        if offset is not None:
            params["offset"] = offset
        if before is not None:
            before = ensure_datetime_or_id(before, "%Y-%m-%d %H:%M:%S")
            if isinstance(before, datetime.datetime):
                before = time_snowflake(before, high=False)
            params["max_id"] = before
        if after is not None:
            after = ensure_datetime_or_id(after, "%Y-%m-%d %H:%M:%S")
            if isinstance(after, datetime.datetime):
                after = time_snowflake(after, high=False)
            params["min_id"] = after
        if content is not None:
            params["content"] = content
        if channel_id is not None:
            params["channel_id"] = channel_id
        if author_id is not None:
            params["author_id"] = author_id
        if pinned is not None:
            params["pinned"] = int(pinned)
        if link_hostname is not None:
            params["link_hostname"] = link_hostname
        if sort_by is not None:
            params["sort_by"] = sort_by
        if sort_order is not None:
            params["sort_order"] = sort_order
        resp = await self.bot.http.request(r, params=params)

        # populate threads if present
        if "threads" in resp:
            for thread_data in resp["threads"]:
                thread = disnake.Thread(guild=guild, state=guild._state, data=thread_data)
                guild._add_thread(thread)

        # build message objects
        messages = []
        for msg_data in itertools.chain.from_iterable(resp["messages"]):
            channel = await self.bot.get_or_fetch_channel(msg_data["channel_id"])
            msg = self.bot._connection.create_message(channel=channel, data=msg_data)
            if not is_public_to_roles(channel.guild, [constants.MEMBER_ROLE_ID, constants.PLAYER_ROLE_ID], channel):
                continue
            messages.append(msg)
        messages = sorted(messages, key=lambda m: m.id)

        # render messages
        def search_chat_prompt(message: disnake.Message) -> str:
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M")
            prompt = (
                f"In {message.channel.name} ({message.channel.id})\n{message.author.display_name} @"
                f" {timestamp}\n{message.clean_content}"
            )
            return prompt

        message_results = "\n\n".join(search_chat_prompt(m) for m in messages)

        # render search meta
        return f"# Search Results\n{resp['total_results']} results\n\n{message_results}"


def is_public_to_roles(guild: Guild, role_ids: list[int], channel, reduce=any):
    return reduce(channel.permissions_for(guild.get_role(r)).view_channel for r in role_ids)


def ensure_datetime_or_id(x: str, strptime_fmt="%Y-%m-%d %H:%M:%S"):
    try:
        return datetime.datetime.strptime(x, strptime_fmt)
    except ValueError:
        try:
            return int(x)
        except ValueError:
            raise ValueError(f"Cannot interpret {x!r} as a datetime in {strptime_fmt} format or a message ID") from None
