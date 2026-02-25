import logging
import os
import os.path as osp
import random
import sys
import time

import discord
from discord.ext import commands

from util.data.hashing import Hashing

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bot")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
current_dir = osp.dirname(osp.abspath(__file__))
data_path = "data"

# ---------------------------------------------------------------------------
# Extensions (cogs) to load
# ---------------------------------------------------------------------------
EXTENSIONS = [
    "cogs.background",
    "cogs.errors",
    "cogs.misc",
    "cogs.reactor",
    "cogs.utility",
    "cogs.verification",
]

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """Load and validate required configuration from environment variables."""
    required_keys = ["token", "key", "used_emails", "hash_key"]
    config: dict = {}
    missing: list[str] = []

    for key in required_keys:
        value = os.environ.get(key)
        if value is None or value == "":
            missing.append(key)
        else:
            config[key] = value

    if missing:
        log.critical("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    return config


config = load_config()

# Seed the RNG from system time
random.seed(int(time.time()))

# Resolve the used-emails file path
used_emails_path = osp.join(current_dir, data_path, config["used_emails"])

# Set up hashing with the configured salt
hashing = Hashing(config["hash_key"])

# ---------------------------------------------------------------------------
# Intents — explicitly enable every privileged intent the bot needs
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True          # Privileged — must be enabled in Developer Portal
intents.message_content = True  # Privileged — must be enabled in Developer Portal
intents.messages = True
intents.reactions = True


# ---------------------------------------------------------------------------
# Bot subclass — the modern way to organise a discord.py bot
# ---------------------------------------------------------------------------
class VerificationBot(commands.Bot):
    """Custom Bot subclass with setup_hook for async extension loading."""

    def __init__(self) -> None:
        def _prefix(bot: commands.Bot, message: discord.Message) -> str:
            pfx = config["key"]
            # Allow an optional space after the prefix  (e.g. "! email" == "!email")
            if message.content.startswith(f"{pfx} "):
                return f"{pfx} "
            return pfx

        super().__init__(
            command_prefix=_prefix,
            intents=intents,
            help_command=None,  # disable the default help; the bot uses vhelp
        )

        # Attach shared state so cogs can access them via self.bot.*
        self.current_dir: str = current_dir
        self.data_path: str = data_path
        self.hashing: Hashing = hashing

    async def setup_hook(self) -> None:
        """Called once before the bot connects. Load all extensions here."""
        loaded = 0
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Cog  | Loaded %s", ext)
                loaded += 1
            except Exception:
                log.exception("Cog  | FAILED to load %s", ext)
        log.info("Loaded %d/%d cogs", loaded, len(EXTENSIONS))

    async def on_ready(self) -> None:
        prefix = config["key"]
        activity = discord.Activity(
            name=f"{prefix}vhelp for verification help",
            type=discord.ActivityType.watching,
        )
        await self.change_presence(activity=activity)
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        await self.process_commands(message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    bot = VerificationBot()
    bot.run(config["token"], log_handler=None)  # log_handler=None: we configured logging ourselves


if __name__ == "__main__":
    main()
