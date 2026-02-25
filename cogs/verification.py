import logging
import os
import os.path as osp
import smtplib
import ssl
import random
import time

import discord
from discord.ext import commands

from util.email import is_valid_email

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


class Verification(commands.Cog):
    """Core email-based verification workflow."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        try:
            self.bot_key: str = os.environ["key"]
            self.used_emails_file: str = os.environ["used_emails"]
            self.warn_emails_file: str = os.environ["warn_emails"]
            self.moderator_email: str = os.environ["moderator_email"]

            self.sample_username: str = os.environ["sample"]

            # Multi-domain: accept a comma-separated list, e.g. "uvic.ca, student.uvic.ca"
            raw_domains = os.environ["domain"]
            self.verify_domains: list[str] = [
                d.strip().lower() for d in raw_domains.split(",") if d.strip()
            ]
            if not self.verify_domains:
                raise ValueError("Environment variable 'domain' must contain at least one domain.")
            # Primary domain — used for sample text in help / error messages
            self.verify_domain: str = self.verify_domains[0]

            self.email_from: str = os.environ["from"]
            self.email_password: str = os.environ["password"]
            self.email_subject: str = os.environ["subject"]
            self.email_server: str = os.environ["server"]
            self.email_port: int = int(os.environ["port"])

            self.role: str = os.environ["server_role"]
            self.channel_id: int = int(os.environ["channel_id"])
            self.notify_id: int = int(os.environ["notify_id"])
            self.admin_id: int = int(os.environ["admin_id"])
            self.author_name: str = os.environ["author_name"]
            self.webmail_link: str = os.environ["webmail_link"]

            # Optional ticket channel — falls back to admin DM for reverification.
            ticket_raw = os.environ.get("ticket_id", "")
            if ticket_raw:
                self.ticket_id: int | None = int(ticket_raw)
            else:
                self.ticket_id = None

            # Token TTL: how many seconds before an unverified token expires (default 15 min)
            self.token_ttl_seconds: float = float(os.environ.get("TOKEN_TTL_MINUTES", "15")) * 60

            self.used_emails_path: str = osp.join(self.bot.current_dir, self.bot.data_path, self.used_emails_file)
            self.warn_emails_path: str = osp.join(self.bot.current_dir, self.bot.data_path, self.warn_emails_file)

        except KeyError as e:
            log.critical("Verification config error — missing env var: %s", e)
            raise

        # In-memory state for active verification sessions
        self.token_list: dict[int, str] = {}
        self.token_times: dict[int, float] = {}   # monotonic timestamps of token issuance
        self.email_list: dict[int, str] = {}
        self.email_attempts: dict[int, int] = {}
        self.verify_attempts: dict[int, int] = {}

        # Ensure data directory exists
        data_dir = osp.join(self.bot.current_dir, self.bot.data_path)
        os.makedirs(data_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _send_email(self, recipient: str, body: str) -> None:
        """Send an email via SMTP. Handles both SSL (port 465) and STARTTLS (port 587)."""
        context = ssl.create_default_context()

        if self.email_port == 465:
            # Port 465 = implicit SSL — use SMTP_SSL directly
            with smtplib.SMTP_SSL(self.email_server, self.email_port, context=context) as server:
                server.login(self.email_from, self.email_password)
                server.sendmail(self.email_from, recipient, body)
        else:
            # Port 587 (or other) = STARTTLS upgrade
            with smtplib.SMTP(self.email_server, self.email_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.email_from, self.email_password)
                server.sendmail(self.email_from, recipient, body)

    def _increment_attempts(self, store: dict[int, int], user_id: int) -> int:
        """Increment and return the attempt count for a user."""
        store[user_id] = store.get(user_id, 0) + 1
        return store[user_id]

    def _resolve_role(self, guild: discord.Guild) -> discord.Role | None:
        """Resolve the verification role by name first, then by ID."""
        role = discord.utils.get(guild.roles, name=self.role)
        if role is None:
            role = discord.utils.find(lambda r: str(r.id) == str(self.role), guild.roles)
        return role

    async def _check_emails_file(self, ctx: commands.Context, email: str) -> bool:
        """Return True (and notify the user) if *email* has already been used."""
        try:
            with open(self.used_emails_path, "r") as f:
                if any(self.bot.hashing.check_hash(email.lower(), line.strip()) for line in f):
                    if self.ticket_id is not None:
                        ticket_channel = ctx.guild.get_channel(self.ticket_id)
                        await ctx.send(
                            f"Error, that email has already been used {ctx.author.mention}! "
                            f"If you believe this is an error or are trying to re-verify, "
                            f"please create a ticket in {ticket_channel.mention}. "
                            f"With it, include your {self.sample_username} and a screenshot of "
                            f"the 4-digit code from your email from when you first verified. Thank you!"
                        )
                    else:
                        admin = await self.bot.fetch_user(self.admin_id)
                        await ctx.send(
                            f"Error, that email has already been used {ctx.author.mention}! "
                            f"If you believe this is an error or are trying to re-verify, "
                            f"please contact {admin.mention} in this channel or through "
                            f"direct message. Thank you!"
                        )
                    return True
            return False
        except FileNotFoundError:
            log.info("Used-emails file does not exist yet — no duplicates possible.")
            return False

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _domains_display(self) -> str:
        """Return a human-readable list of accepted domains for use in messages."""
        return ", ".join(f"`@{d}`" for d in self.verify_domains)

    @commands.command(name="vhelp", aliases=["helpme", "help_me", "verify_help", "Vhelp", "Helpme", "Help_me", "Verify_help"])
    async def verify_help(self, ctx: commands.Context, *args) -> None:
        """How to verify."""
        verify_channel = ctx.guild.get_channel(self.channel_id)

        if len(self.verify_domains) == 1:
            domain_note = f"the bot only accepts email addresses ending in `@{self.verify_domain}`"
        else:
            domain_note = f"the bot accepts email addresses from the following domains: {self._domains_display()}"

        await ctx.send(
            f"To use this bot, please use `{self.bot_key}email {self.sample_username}@{self.verify_domain}` "
            f"in {verify_channel.mention} to receive an email with a **4 digit verification token.** "
            f"Replace `{self.sample_username}@{self.verify_domain}` with your own email, keeping in mind that "
            f"{domain_note}. "
            f"**Wait for an email to be received**. If you don't receive an email after 5 minutes, try using "
            f"the email command again. **Send the command provided in the email** as a message in the "
            f"{verify_channel.mention} channel to gain access to the rest of the server."
            f"\n\n**You can access your webmail at {self.webmail_link}**"
            f"\nMake sure to check your junk email folder for the message in case it gets sent there."
            f"\n\n**Send messages in the {verify_channel.mention} channel to use this bot's commands, "
            f"not in a DM.**"
        )

    @commands.command(name="email", aliases=["mail", "send", "Email", "Mail", "Send"])
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def _email(self, ctx: commands.Context, arg: str) -> None:
        """Send a verification token to the given email address."""
        if ctx.channel.id != self.channel_id:
            return

        # Strip all surrounding whitespace before any processing
        arg = arg.strip()

        log.info("Email request from %s (%s) — address: %s", ctx.author.name, ctx.author.id, arg)
        await ctx.message.delete()

        # Rate-limit check
        if self.email_attempts.get(ctx.author.id, 0) >= MAX_ATTEMPTS:
            await ctx.send(
                f"{ctx.author.mention}, you have exceeded the maximum number of command uses. "
                f"Please contact a moderator for assistance with verifying if this is in error. Thanks!"
            )
            notify = ctx.guild.get_channel(self.notify_id)
            await notify.send(f"Alert! User {ctx.author.mention} has exceeded the amount of `!email` command uses.")
            return

        # Parse and normalise the domain (case-insensitive)
        if "@" not in arg:
            await ctx.send("Error! That is not a valid email!")
            return
        domain = arg.split("@", 1)[1].lower()

        # Validate email format
        if not is_valid_email(arg):
            await ctx.send("Error! That is not a valid email!")
            return

        # Blacklisted sample username
        if arg.lower().startswith(self.sample_username.lower()):
            await ctx.send(
                f"{ctx.author.mention} Use your own email, not the sample one. "
                f"Please try again with your own email."
            )
            return

        # Check warning list
        try:
            with open(self.warn_emails_path, "r") as f:
                if any(arg.lower() == line.strip().lower() for line in f):
                    notify = ctx.guild.get_channel(self.notify_id)
                    await notify.send(
                        f"Alert! Email on warning list used. Discord ID: {ctx.author.mention}, email `{arg}`."
                    )
        except FileNotFoundError:
            log.info("Warning-list file not found — skipping.")

        # Check for previously used email
        if await self._check_emails_file(ctx, arg):
            return

        # Domain must be in the accepted list
        if domain not in self.verify_domains:
            await ctx.send(
                f"Invalid email submitted, {ctx.author.mention}! "
                f"Please submit an email from one of the accepted domains: {self._domains_display()}."
            )
            return

        # Send the verification email
        try:
            await ctx.send("Sending verification email...")
            token = random.randint(1000, 9999)
            self.token_list[ctx.author.id] = str(token)
            self.token_times[ctx.author.id] = time.monotonic()
            self.email_list[ctx.author.id] = arg
            verify_channel = ctx.guild.get_channel(self.channel_id)

            message_text = (
                f"Hello {self.author_name}! Thank you for joining our Discord server!\n\n"
                f"The command to use in the #{verify_channel.name} channel is: {self.bot_key}verify {token}\n\n"
                f"You can copy and paste that command into the #{verify_channel.name} channel to verify.\n\n"
                f"This message was sent by a Discord verification bot.\n"
                f"If you did not request to verify, please contact {self.moderator_email} to let us know."
            )
            full_message = f"Subject: {self.email_subject}\n\n{message_text}"

            self._send_email(arg, full_message)
        except Exception as e:
            await ctx.send("Error! Verification email not sent. Moderators have been informed automatically. Please wait.")
            notify = ctx.guild.get_channel(self.notify_id)
            await notify.send(f"Alert! Bot has encountered an exception. Traceback: {e}")
            log.exception("Failed to send verification email to %s", arg)
            return

        await ctx.send(
            f"Verification email sent to {ctx.author.mention}, please use "
            f"`{self.bot_key}verify ####`, where `####` is the token, to verify.\n"
            f"If you can't find the email, please check your 'Junk Email' folder before "
            f"contacting the moderation team."
        )
        self._increment_attempts(self.email_attempts, ctx.author.id)

    @commands.command(name="verify", aliases=["token", "Verify", "Token"])
    @commands.guild_only()
    async def _verify(self, ctx: commands.Context, arg: str) -> None:
        """Verify with the 4-digit token that was emailed."""
        if ctx.channel.id != self.channel_id:
            return

        # Strip all surrounding whitespace before processing
        arg = arg.strip()

        log.info("Verify attempt from %s (%s) — token: %s", ctx.author.name, ctx.author.id, arg)
        await ctx.message.delete()

        # Rate-limit check
        if self.verify_attempts.get(ctx.author.id, 0) >= MAX_ATTEMPTS:
            await ctx.send(
                f"{ctx.author.mention}, you have exceeded the maximum number of command uses. "
                f"Please contact a moderator for assistance with verifying if this is in error. Thanks!"
            )
            notify = ctx.guild.get_channel(self.notify_id)
            await notify.send(f"Alert! User {ctx.author.mention} has exceeded the amount of `!verify` command uses.")
            return

        # Make sure there's an active session for this user
        if ctx.author.id not in self.token_list:
            await ctx.send(
                f"{ctx.author.mention}, you don't have an active verification session. "
                f"Please use `{self.bot_key}email` first."
            )
            return

        # Token TTL check — expire stale sessions
        elapsed = time.monotonic() - self.token_times.get(ctx.author.id, 0.0)
        if elapsed > self.token_ttl_seconds:
            self.token_list.pop(ctx.author.id, None)
            self.token_times.pop(ctx.author.id, None)
            self.email_list.pop(ctx.author.id, None)
            ttl_minutes = int(self.token_ttl_seconds // 60)
            await ctx.send(
                f"{ctx.author.mention}, your verification token has expired (tokens are valid for "
                f"{ttl_minutes} minute{'s' if ttl_minutes != 1 else ''}). "
                f"Please use `{self.bot_key}email` again to request a new one."
            )
            return

        # Double-check the email hasn't been used since the token was issued
        if await self._check_emails_file(ctx, self.email_list[ctx.author.id]):
            return

        # Token match
        if self.token_list[ctx.author.id] == arg:
            role = self._resolve_role(ctx.guild)
            if role is None:
                log.error("Verification role '%s' not found in guild %s!", self.role, ctx.guild.id)
                await ctx.send("Error! Verification role not found. Please contact a moderator.")
                return

            await ctx.author.add_roles(role)

            with open(self.used_emails_path, "a") as f:
                hashed = self.bot.hashing.hash(self.email_list[ctx.author.id])
                f.write(f"{hashed}\n")

            self.token_list.pop(ctx.author.id)
            self.token_times.pop(ctx.author.id, None)
            self.email_list.pop(ctx.author.id, None)
            await ctx.send(f"{ctx.author.mention}, you've been verified!")
            log.info("User %s (%s) verified successfully.", ctx.author.name, ctx.author.id)
        else:
            await ctx.send(
                f"Invalid token submitted, {ctx.author.mention}! "
                f"Please submit the 4-digit token sent to your email to verify."
            )
            self._increment_attempts(self.verify_attempts, ctx.author.id)

    @commands.command(name="mod_verify", aliases=["manual_verify", "modverify", "manualverify", "addemail", "verifyadd"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def _manual_verify(self, ctx: commands.Context, email: str, userid: int) -> None:
        """Manually verify a user and add their email to the used list."""
        log.info("Manual verify by %s: email=%s userid=%s", ctx.author.name, email, userid)

        # Check if already used
        try:
            with open(self.used_emails_path, "r") as f:
                if any(self.bot.hashing.check_hash(email.lower(), line.strip()) for line in f):
                    await ctx.send(f"{ctx.author.mention}, the email {email} is already in the used emails list.")
                    return
        except FileNotFoundError:
            log.info("Used-emails file not created yet — continuing.")

        # Fetch the member from the guild so we can add roles
        member = ctx.guild.get_member(userid)
        if member is None:
            try:
                member = await ctx.guild.fetch_member(userid)
            except discord.NotFound:
                await ctx.send(f"{ctx.author.mention}, the user with id {userid} was not found in this server.")
                return

        role = self._resolve_role(ctx.guild)
        if role is None:
            await ctx.send("Error! Verification role not found. Please check the configuration.")
            return

        await member.add_roles(role)

        with open(self.used_emails_path, "a") as f:
            hashed = self.bot.hashing.hash(email)
            f.write(f"{hashed}\n")

        log.info("Manually verified user %s with email %s", userid, email)
        await ctx.send(f"{ctx.author.mention}, the user {member.mention} has been manually verified with the email {email}.")

    @commands.command(name="active_tokens", aliases=["verify_in_progress", "in_progress", "activetokens", "verifyinprogress", "inprogress"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def _active_tokens(self, ctx: commands.Context) -> None:
        """Show active verification tokens (mod command)."""
        if not self.token_list:
            await ctx.send("No active verification tokens.")
            return

        friendly = {f"<@{uid}>": token for uid, token in self.token_list.items()}
        await ctx.send(f"Active verification tokens:\n{friendly}")

    @commands.command(name="resetattempts", aliases=["resetattempt", "clearattempts"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def _reset_attempts(self, ctx: commands.Context, member: discord.Member) -> None:
        """Reset the email/verify attempt counters for a user so they can try again."""
        uid = member.id
        email_count = self.email_attempts.pop(uid, 0)
        verify_count = self.verify_attempts.pop(uid, 0)
        log.info(
            "Attempt counters reset for %s (%s) by %s — cleared %d email + %d verify attempts",
            member.name, uid, ctx.author.name, email_count, verify_count,
        )
        await ctx.send(
            f"{ctx.author.mention}, attempt counters reset for {member.mention}. "
            f"(Cleared {email_count} email attempt(s) and {verify_count} verify attempt(s).)"
        )

    @commands.command(name="unverify", aliases=["Unverify", "removeverify", "deverify"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def _unverify(self, ctx: commands.Context, member: discord.Member, email: str = None) -> None:
        """Remove the verified role from a user, and optionally scrub their email hash.

        Usage:
          !unverify @user            — strips the role only
          !unverify @user their@email.com — strips the role and removes the email from the used list
        """
        role = self._resolve_role(ctx.guild)
        if role is None:
            await ctx.send("Error! Verification role not found. Please check the configuration.")
            return

        # Remove the role
        if role in member.roles:
            await member.remove_roles(role, reason=f"Unverified by {ctx.author}")
            role_msg = f"Removed the **{role.name}** role from {member.mention}."
        else:
            role_msg = f"{member.mention} did not have the **{role.name}** role."

        # Optionally remove the email hash from the used-emails file
        hash_msg = ""
        if email:
            email = email.strip().lower()
            target_hash = self.bot.hashing.hash(email)
            try:
                with open(self.used_emails_path, "r") as f:
                    lines = f.readlines()

                new_lines = [l for l in lines if l.strip() != target_hash]
                removed = len(lines) - len(new_lines)

                with open(self.used_emails_path, "w") as f:
                    f.writelines(new_lines)

                if removed:
                    hash_msg = f" Removed {removed} matching email hash(es) from the used-emails list."
                    log.info("Removed %d hash(es) for email %s from used-emails file.", removed, email)
                else:
                    hash_msg = " Email hash was not found in the used-emails list (already absent or wrong email)."
            except FileNotFoundError:
                hash_msg = " Used-emails file does not exist yet — nothing to remove."
        else:
            hash_msg = (
                " Note: the email address was **not** removed from the used-emails list. "
                f"If this user needs to re-verify with the same email, run: "
                f"`{self.bot_key}unverify {member.mention} their@email.com`"
            )

        log.info("Unverify: %s unverified %s (%s). Email arg: %s", ctx.author.name, member.name, member.id, email)
        await ctx.send(f"{role_msg}{hash_msg}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))
