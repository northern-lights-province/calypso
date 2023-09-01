import urllib.parse
from io import BytesIO
from typing import Annotated, Optional, TYPE_CHECKING

import disnake
from kani import AIParam, ChatMessage, ChatRole, Kani, ai_function

from .webutils import get_links, web_markdownify, web_summarize

if TYPE_CHECKING:
    from calypso import Calypso
    from playwright.async_api import Browser, BrowserContext, Page


class AIKani(Kani):
    def __init__(self, *args, bot: "Calypso", browser: "Browser", channel_id: int, chat_session_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.channel_id = channel_id
        self.chat_session_id = chat_session_id
        self.chat_title = None
        # web
        self.max_webpage_len = 1024
        self.browser = browser
        self.context = None
        self.page = None

    @property
    def last_user_message(self) -> ChatMessage | None:
        return next((m for m in self.chat_history if m.role == ChatRole.USER), None)

    # ==== web ====
    # browser management
    async def get_context(self) -> "BrowserContext":
        """Return the browser context if it's initialized, else create and save a context."""
        if self.context:
            return self.context
        self.context = await self.browser.new_context()
        return self.context

    async def get_page(self, create=True) -> Optional["Page"]:
        """Get the current page.

        Returns None if the browser is not on a page unless `create` is True, in which case it creates a new page.
        """
        if self.page is None and create:
            context = await self.get_context()
            self.page = await context.new_page()
        return self.page

    async def goto_page(self, *args, **kwargs):
        page = await self.get_page()
        retval = await page.goto(*args, **kwargs)
        # send a screenshot to the thread
        screenshot_bytes = await page.screenshot()
        channel = await self.bot.get_or_fetch_channel(self.channel_id)
        embed = disnake.Embed(title=await page.title(), url=page.url, colour=disnake.Colour.blurple())
        embed.set_image(url="attachment://screenshot.png")
        screenshot = disnake.File(BytesIO(screenshot_bytes), filename="screenshot.png")
        await channel.send(embed=embed, file=screenshot)
        return retval

    # browsing
    @ai_function()
    async def search(
        self,
        query: str,
        new_tab: Annotated[bool, AIParam("Whether to search in a new tab or the current tab.")] = False,
    ):
        """Search a query on Google."""
        if new_tab:
            context = await self.get_context()
            self.page = await context.new_page()
        query_enc = urllib.parse.quote_plus(query)
        await self.goto_page(f"https://www.google.com/search?q={query_enc}")
        # content
        search_text = await self.page.inner_text("#main")
        if "Content Navigation Bar" in search_text:
            _, search_text = search_text.split("Content Navigation Bar", 1)
        # links
        search_loc = self.page.locator("#search")
        links = await get_links(search_loc)
        return f"{search_text.strip()}\n\n===== Links =====\n{links.model_dump_json(indent=2)}"

    @ai_function()
    async def visit_page(self, href: str):
        """Visit a web page and view its contents."""
        await self.goto_page(href)
        page = await self.get_page()
        # header
        title = await page.title()
        header = f"{title}\n{'=' * len(title)}\n\n"
        # content
        content_html = await page.inner_html("body")
        content = web_markdownify(content_html, page.url)
        # summarization
        if self.message_token_len(ChatMessage.function("visit_page", content)) > self.max_webpage_len:
            if last_user_msg := self.last_user_message:
                content = await web_summarize(
                    content,
                    task=(
                        "Please summarize the main content of the webpage above.\n"
                        f"Keep the current goal in mind: {last_user_msg.content}"
                    ),
                )
            else:
                content = await web_summarize(content)
        result = header + content
        return result

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
