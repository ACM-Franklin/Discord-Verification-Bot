import discord
from discord.ext import commands


class Misc(commands.Cog):
    """Miscellaneous informational commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.github_link = "https://github.com/jensengillett/verificationbot"

    @commands.command(aliases=["coffee", "buymeacoffee", "paypal", "pp", "cashapp", "source"])
    async def support(self, ctx: commands.Context) -> None:
        """Support development!"""

        embed = discord.Embed(title="Support", color=0x1B7819)
        embed.description = f"[Repository]({self.github_link})"
        embed.timestamp = ctx.message.created_at

        disc_jensen = (
            "Project Owner, Contributor, Maintainer\n"
            "[Ko-fi](https://ko-fi.com/jensengillett)\n"
            "[PayPal](https://paypal.me/jensengillett)"
        )
        embed.add_field(name="Jensen", value=disc_jensen, inline=False)

        desc_mark = (
            "Contributor, Maintainer, Initial Author\n"
            "[Ko-fi](https://ko-fi.com/miningmark48)\n"
            "[CashApp](https://cash.app/$MiningMark48)"
        )
        embed.add_field(name="Mark", value=desc_mark, inline=False)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Misc(bot))
