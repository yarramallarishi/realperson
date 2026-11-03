# OmniBot project status

## Milestone 1 — runnable foundation

Completed:

- Project structure, Python dependencies, environment template, ignore rules, and Docker Compose.
- Async SQLAlchemy persistence with SQLite by default and PostgreSQL-compatible URLs.
- FastAPI Discord OAuth login with server-side sessions and encrypted OAuth tokens, guild
  authorization, short-lived cached permission checks, configuration, and analytics.
- Initial Alembic schema migration and PostgreSQL-aware migration environment.
- Discord bot startup, Groq provider, `/ask`, conversation reset, moderation commands, opt-in
  message automod, moderation log channel, suspicious-join logging, and welcome/goodbye events.
- React/TypeScript/Vite/Tailwind dashboard with Discord login, server selector, editable settings,
  loading/error states, and an analytics chart.
- Optional same-origin static dashboard serving from FastAPI and a Windows Cloudflare Quick Tunnel
  launcher for public access without a domain.
- Focused backend tests for permissions, config validation, and session settings.

Known scope limits:

- Tickets/transcripts, role menus, XP/rewards, giveaways, persistent poll management, reminders,
  custom embeds, and advanced audit-log integrations are not yet implemented. `/poll` currently
  creates a basic two-option reaction poll only.
- Suspicious join bursts are recorded and logged; automatic raid containment is not enabled.
- The dashboard currently exposes general guild, AI, automod, and welcome configuration plus analytics;
  dedicated editors for all community modules are not yet implemented.
- Local development creates missing tables automatically. Production startup expects the database
  migration to have run; the Compose API service runs `alembic upgrade head` before startup.
- Deployment is containerized but provider-specific free-tier deployment manifests are not included.
- Cloudflare Quick Tunnel URLs are temporary; Discord OAuth Redirects must be updated after a new
  tunnel starts. The local computer must stay online.

Commands checked:

- `python -m pytest -q` — 8 passed.
- `python -m compileall -q omnibot migrations tests` — passed.
- Python imports for API, bot, and cogs — passed.
- Loaded all Discord extensions without connecting; 14 slash commands registered.
- `npm.cmd run build` in `frontend/` — passed with a lightweight SVG chart and no large chart dependency.
- `alembic upgrade head` and `alembic current` — passed on SQLite; revision `5a04ff9cc754`.
- FastAPI TestClient smoke checks — startup, health, unauthenticated access rejection, and logout passed.
- Cloudflare Quick Tunnel launcher and `cloudflared` installation verified on Windows.
- Public tunnel dashboard returned HTTP 200 and `/auth/login` returned HTTP 307.
- API and Discord bot started successfully through the Quick Tunnel launcher.
- Discord OAuth callback must be added to the Developer Portal before users can finish sign-in.
- Discord guild-list rate limiting was causing API 502s; access checks now share a per-session
  30-second cache and Discord rate limits return a retryable 503.

Validation notes:

- The available interpreter was Python 3.13.15; repeat the checks with Python 3.12 before release.
- Live Discord OAuth, Gateway, Groq calls, and Docker image startup were not exercised because no
  application credentials or container runtime were configured in this workspace.

## Exact next task

Implement and test the community interaction modules (tickets with transcripts, self-role menus,
polls, giveaways, reminders, and XP/leaderboards), then expose their settings in the dashboard.
