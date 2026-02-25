import copy
import logging

from discord.ext import commands
from discord.ext.commands import errors as cmderr

from util.email import is_valid_email

log = logging.getLogger(__name__)


class Errors(commands.Cog):
    """Global command-error handler with smart fallback for mistyped verification commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener("on_command_error")
    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError) -> None:
        if isinstance(exception, cmderr.PrivateMessageOnly):
            await ctx.send("Please DM the bot to use this command!")
        elif isinstance(exception, cmderr.NoPrivateMessage):
            await ctx.send("This command must be used in a Discord server!")
        elif isinstance(exception, cmderr.MissingRole):
            await ctx.send("Missing required role to use this command!")
        elif isinstance(exception, cmderr.MissingPermissions):
            await ctx.send("You do not have permission to use this command!")
        elif isinstance(exception, cmderr.MissingRequiredArgument):
            await ctx.send("Missing required arguments!")
        elif isinstance(exception, cmderr.UserInputError):
            await ctx.send("Missing or invalid argument!")
        elif isinstance(exception, cmderr.CommandOnCooldown):
            await ctx.send(f"This command is on cooldown. Try again in {exception.retry_after:.1f}s.")
        elif isinstance(exception, cmderr.CommandNotFound):
            await self._try_fallback(ctx)
        else:
            log.exception("Unhandled command error in '%s'", ctx.command, exc_info=exception)

    async def _try_fallback(self, ctx: commands.Context) -> None:
        """Attempt to interpret an unknown command as a bare email or token."""
        content = ctx.message.content.replace(ctx.prefix, "", 1)

        def clean_aliases(text: str, aliases: list[str]) -> str:
            for alias in aliases:
                alias = alias.lower()
                if text.startswith(alias):
                    text = text.replace(f"{alias} ", "", 1).replace(alias, "", 1)
                    break
            return text.strip()

        async def invoke_cmd(cmd, cleaned_content: str) -> None:
            msg = copy.copy(ctx.message)
            msg.content = cleaned_content
            new_ctx = await self.bot.get_context(msg)
            await new_ctx.invoke(cmd, cleaned_content)

        email_cmd = self.bot.get_command("email")
        if email_cmd is not None:
            cleaned = clean_aliases(content, email_cmd.aliases)
            if is_valid_email(cleaned):
                return await invoke_cmd(email_cmd, cleaned)

        verify_cmd = self.bot.get_command("verify")
        if verify_cmd is not None:
            cleaned = clean_aliases(content, verify_cmd.aliases)
            if len(cleaned) == 4 and cleaned.isnumeric():
                return await invoke_cmd(verify_cmd, cleaned)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Errors(bot))
