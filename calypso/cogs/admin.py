import io
import textwrap
import traceback
from contextlib import redirect_stdout

from disnake.ext import commands

ADMIN_IDS = [187421759484592128, 197519973650923520]


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    def get_syntax_error(self, e):
        return "```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```".format(e, "^", type(e).__name__)

    @commands.command(hidden=True, name="e")
    async def _eval(self, ctx, *, body: str):
        """Evaluates some code"""
        if ctx.author.id not in ADMIN_IDS:
            return

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.message.channel,
            "author": ctx.message.author,
            "guild": ctx.message.guild,
            "message": ctx.message,
        }
        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = "async def func():\n{}".format(textwrap.indent(body, "  "))

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send("```py\n{}: {}\n```".format(e.__class__.__name__, e))

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send("```py\n{}{}\n```".format(value, traceback.format_exc()))
        else:
            value = stdout.getvalue()
            if ret is None:
                if value:
                    await ctx.send("```py\n{}\n```".format(value))
            else:
                await ctx.send("```py\n{}{}\n```".format(value, ret))


def setup(bot):
    bot.add_cog(Admin(bot))
