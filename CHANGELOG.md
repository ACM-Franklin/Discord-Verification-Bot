# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Multi-domain support** — `domain` env var now accepts a comma-separated list (e.g. `uvic.ca, student.uvic.ca`). All accepted domains are shown in `!vhelp` and error messages.
- **Token TTL** — Verification tokens now expire after a configurable window. Set via `TOKEN_TTL_MINUTES` env var (default: `15`). Expired tokens produce a clear user-facing message prompting them to re-request.
- **`!resetattempts @user`** — Mod command (requires `manage_messages`) to clear a user's email and verify attempt counters without restarting the bot.
- **`!unverify @user [email]`** — Mod command (requires `manage_messages`) to strip the verified role from a user. If the email address is provided, the corresponding hash is also removed from the used-emails file, enabling clean re-verification.
- **`!email` cooldown** — Built-in per-user 60-second cooldown on the `!email` command to prevent token spam.
- **`active_tokens` restricted to moderators** — `!active_tokens` now requires `manage_messages` to prevent leaking session data to regular users.
- **Structured logging** — All `print()` calls replaced with Python `logging` throughout `bot.py` and all cogs. Timestamped, levelled output to stdout.
- **`TOKEN_TTL_MINUTES` env var** — Controls token lifetime in minutes. Defaults to 15 if not set.

### Changed
- **`bot.py` rewritten** as a proper `commands.Bot` subclass (`VerificationBot`). Extension loading moved to `async setup_hook()`, eliminating `RuntimeWarning: coroutine 'Bot.load_extension' was never awaited`.
- **All cog `setup()` functions** converted from synchronous `def setup(bot)` to `async def setup(bot)` with `await bot.add_cog(...)`, as required by discord.py 2.x.
- **`intents.message_content = True`** added explicitly. This privileged intent is required for the bot to read message content and was the root cause of commands silently failing.
- **`intents.members = True`** confirmed and documented. Required for member lookups in reaction role assignment.
- **SMTP handling fixed** — Port 465 now uses `smtplib.SMTP_SSL` (implicit SSL) instead of incorrectly attempting `STARTTLS` on an SSL connection. Port 587 continues to use `STARTTLS`.
- **`!mod_verify` bug fixed** — Was reading `self.email_list[ctx.author.id]` (the mod's own in-progress session) instead of the `email` argument passed to the command.
- **Whitespace stripping hardened** — `arg.strip()` applied at the entry point of both `!email` and `!verify` before any processing. Email domain extracted with `split("@", 1)[1].lower()` (splits on first `@` only, normalises case immediately).
- **`!verify` active-session guard** — Now checks that the user has an active token before attempting a lookup (previously would `KeyError` on first verify with no prior email command).
- **`!verify` role-not-found guard** — If the configured verification role cannot be resolved, the user receives a clear error message instead of an unhandled exception.
- **`Utility.start_time`** refactored from a module-level `global` to a proper instance variable on the cog.
- **`Reactor` null-safety** — Role and guild lookups now null-checked before use; role assignment failures are caught and logged rather than crashing the listener.
- **`docker-compose.yml`** — Removed deprecated `version:` key (no longer required by modern Docker Compose).
- **`Dockerfile`** — Base image updated from `python:3` to `python:3.12-slim`. Now installs dependencies via `COPY requirements.txt` + `pip install -r` for proper layer caching.
- **`requirements.txt`** — Pinned `discord.py>=2.3,<3` and `sqlalchemy>=2.0,<3`. Removed unused `varint` dependency.
- **`help_command=None`** passed to `Bot.__init__` instead of calling `bot.remove_command('help')` after construction.
- **`current_dir`** computed with `osp.abspath(__file__)` instead of bare `__file__` to ensure a correct absolute path in all invocation contexts.
- **`README.md`** fully rewritten — updated setup instructions, full configuration reference table, complete command tables including new mod commands, privileged intent requirement explicitly called out.

---

## [0.2.0]

### Added
- `ticket_id` env var — if set, reverification messages direct users to a ticket channel instead of pinging the admin user directly.
- `try`/`except` around email sends — SMTP exceptions are caught and reported to the mod notification channel automatically.
- `!active_tokens` command — lists users with incomplete (token-issued-but-not-verified) sessions. Useful before restarting the bot.
- `!mod_verify` command — allows a moderator to manually grant the verified role and record an email, bypassing the main flow.
- Check for missing data directory — created automatically on startup if absent.

### Fixed
- Token pops from the active list after a successful verification (previously remained until bot restart).
- Hardcoded server-specific strings removed from the email body; all user-facing text is now driven by env vars.
- Random number generator now seeded from system time instead of the bot token (was causing identical tokens across restarts).
- SMTP compatibility improved for servers other than Gmail (tested with Outlook).

---

## [0.1.0]

### Added
- Initial bot implementation by [MiningMark48](https://github.com/MiningMark48).
- Email-based verification flow: `!email` sends a 4-digit token, `!verify` redeems it.
- Per-guild SQLite databases via SQLAlchemy for reactor and configuration storage.
- Reaction role system (`!reactoradd`, `!reactorget`, `!reactordelete`, `!reactorclearall`).
- Dockerfile and Docker Compose configuration for containerised deployment (contributed by [aabuelazm](https://github.com/aabuelazm)).
- Environment variable-driven configuration — no hardcoded secrets.
- MD5+salt hashing of stored email addresses.
- Warning email list — emails on the list trigger a mod-channel alert.
- `!prune` for bulk message deletion.
- `!uptime` to report bot runtime.
- `!vhelp` for user-facing verification instructions.
- `!support` linking to developer support pages and the repository.
- Security fixes by [MNThomson](https://github.com/MNThomson).
