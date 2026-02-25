# VerificationBot

![License](https://img.shields.io/github/license/jensengillett/verificationbot?color=6cc644&label=License&style=flat-square)
![Repo Stars](https://img.shields.io/github/stars/jensengillett/verificationbot?color=6e5494&label=Stars&logo=github&logoColor=white&style=flat-square)

> A Discord verification bot designed for post-secondary institutions. Confirms membership by sending a one-time token to an institutional email address. Fully modular, Docker-native, and configurable via environment variables.

---

- [About](#about)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [Docker (Recommended)](#docker-recommended)
  - [Python Virtual Environment](#python-virtual-environment)
- [Configuration Reference](#configuration-reference)
- [Commands](#commands)
  - [User Commands](#user-commands)
  - [Moderator Commands](#moderator-commands)
  - [Reactor Commands](#reactor-commands)
  - [Input Flexibility](#input-flexibility)
- [Contributors](#contributors)
- [Support Development](#support-development)
- [Legal](#legal)

---

## About

VerificationBot started as a small project for the UVic Engineering and Computer Science Discord server to prevent non-UVic students from accessing the rest of the server. With the help of [MiningMark48](https://github.com/MiningMark48), the initial draft was created. Since then the bot has been expanded, rewritten, and hardened through contributions from the community.

### How It Works

When a user joins the server they have access to a limited set of channels, including a dedicated verification channel. From there, the flow is:

1. **User submits their institutional email:**
   ```
   !email yourname@yourinstitution.edu
   ```

2. **The bot sends a 4-digit token to that address** via your configured SMTP server. The token expires after a configurable window (default: 15 minutes).

3. **User submits the token:**
   ```
   !verify 1234
   ```

4. **If valid**, the user is granted the configured verified role and their email hash is recorded to prevent reuse.

---

## Prerequisites

Before setting up the bot, ensure the following are in order:

### Discord Developer Portal

1. Create a bot application at the [Discord Developer Portal](https://discord.com/developers/applications).
2. Under **Bot → Privileged Gateway Intents**, enable **both**:
   - **Server Members Intent**
   - **Message Content Intent**

   The bot will fail to process commands or see member data without these.

3. When generating the invite URL under **OAuth2**, grant the following permissions:

   | Permission | Required For |
   |---|---|
   | Manage Roles | Assigning the verified role |
   | View Channels | Reading the verification channel |
   | Send Messages | Responding to users |
   | Manage Messages | Deleting email commands to protect privacy |
   | Read Message History | Context for replies |
   | Add Reactions | Reactor role assignment |

### SMTP Email Account

The bot sends verification emails via SMTP. It supports:
- **Port 465** — implicit SSL (e.g. Gmail with App Password)
- **Port 587** — STARTTLS (e.g. Outlook/Exchange)

---

## Setup

### Docker (Recommended)

1. Install [Docker](https://docs.docker.com/get-docker/). Docker Compose is bundled with modern Docker installs.

2. Clone or download this repository.

3. Open `docker-compose.yml` and fill in your environment variables (see [Configuration Reference](#configuration-reference) below).

4. Build and start the container:
   ```bash
   docker compose build
   docker compose up -d
   ```

5. To view logs:
   ```bash
   docker compose logs -f
   ```

The `./data` directory is mounted as a volume, so your used-emails file and SQLite databases persist across restarts.

### Python Virtual Environment

1. Ensure Python 3.12+ is installed.

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux / macOS
   .\venv\Scripts\activate       # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Export the required environment variables (or create a `.env` file and load it). All variables are listed in `docker-compose.yml`.

5. Run the bot:
   ```bash
   python bot.py
   ```

---

## Configuration Reference

All configuration is done via environment variables, set in `docker-compose.yml` (Docker) or your shell environment (venv). No files need to be edited beyond `docker-compose.yml`.

| Variable | Required | Description |
|---|---|---|
| `token` | Yes | Discord bot token from the Developer Portal. Keep this secret. |
| `key` | Yes | Command prefix (e.g. `!` or `$`). |
| `used_emails` | Yes | Filename for storing used email hashes (e.g. `used_emails.txt`). |
| `hash_key` | Yes | Salt used when hashing emails with MD5. Set to any secret string. Leave blank to disable hashing (not recommended). |
| `warn_emails` | No | Filename for a list of emails that should trigger a mod alert when used (e.g. professor addresses). |
| `moderator_email` | Yes | Moderator contact email shown in the verification email footer. |
| `sample` | Yes | Placeholder username shown in `!vhelp` (e.g. `studentid`). Also blacklisted from verification. |
| `domain` | Yes | Accepted email domain(s). Supports **comma-separated values** for multi-domain setups (e.g. `uvic.ca, student.uvic.ca`). |
| `from` | Yes | Email address the bot sends from. |
| `password` | Yes | Password or App Password for the sending email account. |
| `subject` | Yes | Subject line of the verification email (e.g. `Verification`). |
| `server` | Yes | SMTP server hostname (e.g. `smtp.gmail.com`). |
| `port` | Yes | SMTP port. Use `465` for implicit SSL, `587` for STARTTLS. |
| `webmail_link` | Yes | URL to the institution's webmail, shown in `!vhelp`. |
| `server_role` | Yes | Name or ID of the role granted on successful verification. |
| `channel_id` | Yes | ID of the verification channel. |
| `notify_id` | Yes | ID of the mod-alerts channel for bot notifications. |
| `admin_id` | Yes | User ID of the admin to ping for reverification requests (used when `ticket_id` is not set). |
| `author_name` | Yes | Greeting name used in the email body (e.g. your server or institution name). |
| `ticket_id` | No | ID of a ticket channel. If set, reverification requests point here instead of pinging the admin directly. |
| `TOKEN_TTL_MINUTES` | No | How long (in minutes) a verification token remains valid. Defaults to `15`. |

---

## Commands

All commands use the prefix configured in the `key` environment variable. The examples below use `!`.

### User Commands

| Command | Aliases | Description |
|---|---|---|
| `!vhelp` | `helpme`, `help_me`, `verify_help` | Displays instructions for verifying, including the accepted email domain(s). |
| `!email <address>` | `mail`, `send` | Sends a 4-digit verification token to the provided email. Limited to one request per 60 seconds. |
| `!verify <token>` | `token` | Submits the token received by email. Tokens expire after `TOKEN_TTL_MINUTES` minutes. |
| `!uptime` | `up`, `time` | Shows how long the current bot instance has been running. |
| `!support` | `coffee`, `paypal`, `source` | Displays links to the project repository and ways to support the developers. |

### Moderator Commands

Require the **Manage Messages** permission.

| Command | Usage | Description |
|---|---|---|
| `!mod_verify` | `!mod_verify <email> <user_id>` | Manually grants the verified role to a user and records their email, bypassing the email flow. |
| `!active_tokens` | `!active_tokens` | Lists all users with in-progress (unexpired) verification sessions. |
| `!resetattempts` | `!resetattempts @user` | Clears a user's email and verify attempt counters so they can try again without a bot restart. |
| `!unverify` | `!unverify @user [email]` | Removes the verified role from a user. If the email is provided, also removes their hash from the used-emails list, enabling clean re-verification. |
| `!prune` | `!prune <amount>` | Bulk-deletes up to 100 messages in the current channel. Requires **Manage Messages**. |

### Reactor Commands

Require the **Manage Guild** permission. Reactors let users gain or lose roles by reacting to a specific message with a specific emoji.

| Command | Usage | Description |
|---|---|---|
| `!reactoradd` | `!reactoradd <message_id> <role_id> <emoji>` | Attaches a reactor to a message. The bot adds the emoji reaction automatically. |
| `!reactorget` | `!reactorget` | Lists all active reactors in the server. |
| `!reactordelete` | `!reactordelete <message_id>` | Removes all reactors from a specific message. |
| `!reactorclearall` | `!reactorclearall` | Removes all reactors in the server. |

### Input Flexibility

The `!email` command (and its fallback handler) accepts several common mis-formatted variations to assist users unfamiliar with Discord:

| What the user types | Handled? |
|---|---|
| `!email user@domain.edu` | Yes — standard usage |
| `!email user@domain.edu ` | Yes — trailing whitespace stripped |
| `! email user@domain.edu` | Yes — space after prefix |
| `user@domain.edu` | Yes — bare email, no prefix or command word |
| `email user@domain.edu` | Yes — missing prefix |

---

## Contributors

Original author and project maintainer: **[Jensen Gillett (jensengillett)](https://github.com/jensengillett)**

| Contributor | Role |
|---|---|
| [MiningMark48](https://github.com/MiningMark48) | Initial author — wrote the first draft, reactor module, SQLAlchemy data layer, cog rewrite, and miscellaneous features |
| [aabuelazm](https://github.com/aabuelazm) | Wrote the Dockerfile and introduced environment variable configuration for Docker deployment |
| [MNThomson](https://github.com/MNThomson) | Security fixes |

---

## Support Development

If you use this bot on your server, a link back to this repository is appreciated.

To support financially:
- [Ko-fi — Jensen Gillett](https://ko-fi.com/jensengillett)
- [PayPal — Jensen Gillett](https://paypal.me/jensengillett)
- [Ko-fi — MiningMark48](https://ko-fi.com/miningmark48)
- [CashApp — MiningMark48](https://cash.app/$MiningMark48)

---

## Legal

### License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](./LICENSE) file for the full text.

### Disclaimer

This project is not affiliated with [Discord](https://discord.com/) or [discord.py](https://github.com/Rapptz/discord.py).

Maintenance of this project is best-effort. If Discord or discord.py introduce breaking API changes, an update may not be immediate. In the event that support is dropped indefinitely, this repository will be archived and the README updated to reflect that status.
