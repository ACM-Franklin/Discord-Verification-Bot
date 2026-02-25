import logging
import os

from discord.ext import commands

from util.email import is_valid_email

log = logging.getLogger(__name__)


class Background(commands.Cog):
    """Watches the verification channel for bare emails/tokens sent without the command prefix."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        try:
            self.channel_id = int(os.environ["channel_id"])
        except KeyError:
            log.error("Environment variable 'channel_id' is not set — Background cog will not function.")
            self.channel_id = None
        except ValueError:
            log.error("Environment variable 'channel_id' is not a valid integer.")
            self.channel_id = None

    @commands.Cog.listener("on_message")
    async def on_message(self, message) -> None:
        if message.author.bot or self.channel_id is None:
            return

        if message.channel.id != self.channel_id:
            return

        content = str(message.content).lower().strip()

        def clean_aliases(text: str, aliases: list[str]) -> str:
            for alias in aliases:
                alias = alias.lower()
                if text.startswith(alias):
                    text = text.replace(f"{alias} ", "", 1).replace(alias, "", 1)
                    break
            return text.strip()

        async def invoke_cmd(cmd, cleaned_content: str) -> None:
            ctx = await self.bot.get_context(message)
            await ctx.invoke(cmd, cleaned_content)

        # Try to match a bare email (no prefix)
        email_cmd = self.bot.get_command("email")
        if email_cmd is not None:
            cleaned = clean_aliases(content, email_cmd.aliases)
            if is_valid_email(cleaned):
                return await invoke_cmd(email_cmd, cleaned)

        # Try to match a bare 4-digit verification token
        verify_cmd = self.bot.get_command("verify")
        if verify_cmd is not None:
            cleaned = clean_aliases(content, verify_cmd.aliases)
            if len(cleaned) == 4 and cleaned.isnumeric():
                return await invoke_cmd(verify_cmd, cleaned)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Background(bot))
