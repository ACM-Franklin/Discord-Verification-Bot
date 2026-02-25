import datetime
import time

from discord.ext import commands


class Utility(commands.Cog):
    """Utility commands for server management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.start_time: float | None = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.start_time = time.time()

    @commands.command(name="prune", aliases=["purge", "nuke", "Prune", "Purge", "Nuke"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def prune(self, ctx: commands.Context, amt: int) -> None:
        """Bulk delete messages (up to 100)."""
        amt = max(min(amt, 100), 0)
        await ctx.message.delete()
        await ctx.channel.purge(limit=amt)
        msg = await ctx.send(f"Pruned `{amt}` messages.")
        await msg.delete(delay=3)

    @commands.command(name="uptime", aliases=["Uptime", "up-time", "Up-time", "up", "time", "Up", "Time"])
    async def uptime(self, ctx: commands.Context) -> None:
        """Check how long the bot has been running."""
        if self.start_time is None:
            await ctx.send("Bot is still starting up...")
            return

        delta = str(datetime.timedelta(seconds=int(round(time.time() - self.start_time))))
        await ctx.send(f"This bot has been running for {delta}.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
