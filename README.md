# OmniBot

OmniBot is a modular Discord bot and web dashboard. The first implementation milestone provides a
working Discord OAuth dashboard, persistent guild configuration, Groq-powered `/ask`, moderation
commands, basic opt-in automod, welcome messages, and analytics. See [PROJECT_STATUS.md](PROJECT_STATUS.md)
for the exact implemented scope and the next milestone.

## Requirements

- Python 3.12
- Node.js 20+
- A Discord application and bot
- A Groq API key for AI responses

## Windows PowerShell setup

From the project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the values in `.env`. Generate a session secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Install the frontend dependencies and launch the API, bot, and dashboard in three PowerShell
terminals:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

```powershell
# From the project root
.\.venv\Scripts\Activate.ps1
uvicorn omnibot.api.main:app --reload
```

```powershell
# From the project root
.\.venv\Scripts\Activate.ps1
python -m omnibot.bot
```

## Discord and Groq setup

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications).
2. Under **Bot**, create the bot, copy its token into `DISCORD_TOKEN`, and enable **Message Content
   Intent** and **Server Members Intent**. These privileged intents are used for mention chat,
   automod, and welcome events.
3. Under **OAuth2**, add `http://localhost:8000/auth/callback` as a redirect URI. Copy the client ID
   and client secret to `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`.
4. Invite the bot with `bot` and `applications.commands` scopes. Select only the permissions needed
   for your configured features; OmniBot does not request Administrator by default.
5. Create a Groq API key in the Groq console and set `GROQ_API_KEY`. The key stays server-side.

## Local checks

```powershell
pytest
python -m compileall omnibot
cd frontend
npm.cmd run build
```

Open `http://localhost:5173`; sign in with Discord, choose a server where your account has Manage
Server or ownership, and save settings. The API also serves `/health`.

## Docker

Copy and configure `.env`, then run:

```powershell
docker compose up --build
```

The compose stack runs PostgreSQL, the API, the bot, and the dashboard. For a public deployment,
set `DISCORD_REDIRECT_URI`, `FRONTEND_URL`, and `API_BASE_URL` to HTTPS origins and provision a
strong `SESSION_SECRET`. The dashboard should be served behind HTTPS.
For local Compose use, set `FRONTEND_URL=http://localhost:8080` in `.env`; the API applies the
Alembic migrations before accepting requests, and the bot waits for the API health check.
Set a non-placeholder `POSTGRES_PASSWORD` in `.env` before starting Compose.

## Free public access with Cloudflare Quick Tunnel

On Windows, install `cloudflared` once:

```powershell
winget install --id Cloudflare.cloudflared --exact --accept-package-agreements --accept-source-agreements
```

Restart PowerShell after installation. From the project root, run:

```powershell
.\scripts\start-cloudflare.ps1
```

The script builds the dashboard, applies SQLite migrations, creates a temporary Cloudflare HTTPS
URL, and starts the API and bot. The API serves the built dashboard and API from the same origin.
Copy the printed `Discord redirect URI` into **Discord Developer Portal → OAuth2 → Redirects**,
save, then open the printed dashboard URL and sign in. The redirect URL is different each time a
Quick Tunnel starts, so update Discord OAuth2 Redirects whenever the URL changes.

Quick Tunnels require no Cloudflare account or domain, but the URL is temporary and changes after
restart. Your PC must remain on and connected to the internet, and the PowerShell window running
the script must stay open. This is a free temporary public link, not always-on hosting. Never
publish `.env`; keep the bot and API keys private.

## Free hosting notes

Free tiers and eligibility change over time. A practical low-cost setup is a small always-on
container/VM for the bot and API, a free static frontend host, and a free PostgreSQL tier where
available. Many free app tiers sleep and interrupt Discord gateway connections; do not rely on a
sleeping service for a production bot. Review current limits and data-retention policies before
choosing a provider.

## Safety and authorization

Dashboard API routes re-check the signed-in user's Discord server ownership/Manage Server
permission on every guild-scoped request. Moderation slash commands use Discord permission checks
and role hierarchy checks. Kick, ban, purge, and unban require an explicit confirmation argument.
AI is text-only and cannot invoke tools or moderation actions. OAuth access tokens are encrypted in
the database and are never placed in the browser session cookie. Login and settings writes are
rate-limited.
