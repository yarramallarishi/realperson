import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from omnibot.api.schemas import SettingsPatch, validate_section
from omnibot.config import get_settings
from omnibot.db.models import AIUsage, AuthSession, GuildEvent, ModerationCase
from omnibot.db.session import SessionLocal, get_db
from omnibot.services.discord_auth import (
    authorized_guilds, clear_guild_cache, decrypt_access_token, discord_get, encrypt_access_token,
    exchange_code, require_guild_access, require_user,
)
from omnibot.services.guild_settings import get_guild_settings, save_guild_settings
from omnibot.services.rate_limit import enforce_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/auth/login")
async def login(request: Request):
    client_host = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"oauth-login:{client_host}", limit=10, window_seconds=60)
    settings = get_settings()
    if not settings.discord_client_id:
        raise HTTPException(status_code=503, detail="Discord OAuth is not configured")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    query = urlencode({
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    })
    return RedirectResponse(f"https://discord.com/oauth2/authorize?{query}")


@router.get("/auth/callback")
async def callback(request: Request, code: str, state: str):
    expected = request.session.pop("oauth_state", None)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    token_data = await exchange_code(code)
    token = token_data.get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Discord did not return an access token")
    user = await discord_get("/users/@me", token)
    session_id = secrets.token_urlsafe(32)
    expires_in = max(60, int(token_data.get("expires_in", 3600)))
    async with SessionLocal() as db:
        db.add(AuthSession(
            id=session_id,
            user={
                "id": user["id"], "username": user["username"],
                "global_name": user.get("global_name"), "avatar": user.get("avatar"),
            },
            encrypted_access_token=encrypt_access_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        ))
        await db.commit()
    request.session.clear()
    request.session["session_id"] = session_id
    return RedirectResponse(get_settings().frontend_url)


@router.post("/auth/logout")
async def logout(request: Request):
    session_id = request.session.get("session_id")
    clear_guild_cache(session_id)
    token = None
    if session_id:
        async with SessionLocal() as db:
            record = await db.get(AuthSession, session_id)
            if record:
                token = decrypt_access_token(record.encrypted_access_token)
                await db.delete(record)
                await db.commit()
    request.session.clear()
    if token:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://discord.com/api/v10/oauth2/token/revoke",
                    data={
                        "client_id": settings.discord_client_id,
                        "client_secret": settings.discord_client_secret,
                        "token": token,
                        "token_type_hint": "access_token",
                    },
                )
            if response.is_error:
                logger.warning("Discord token revocation failed during logout",
                               extra={"status_code": response.status_code})
        except httpx.HTTPError:
            logger.warning("Discord token revocation request failed during logout")
    return {"ok": True}


@router.get("/api/me")
async def me(user: dict = Depends(require_user)):
    return user


@router.get("/api/guilds")
async def list_guilds(request: Request):
    return await authorized_guilds(request)


@router.get("/api/guilds/{guild_id}/config")
async def guild_config(guild_id: int, request: Request,
                       session: AsyncSession = Depends(get_db)):
    await require_guild_access(request, guild_id)
    return await get_guild_settings(session, guild_id)


@router.patch("/api/guilds/{guild_id}/config/{section}")
async def update_config(guild_id: int, section: str, body: SettingsPatch, request: Request,
                        session: AsyncSession = Depends(get_db),
                        user: dict = Depends(require_user)):
    enforce_rate_limit(f"settings-write:{user['id']}:{guild_id}", limit=30, window_seconds=60)
    await require_guild_access(request, guild_id)
    try:
        values = validate_section(section, body.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await save_guild_settings(session, guild_id, {section: values})
    session.add(GuildEvent(guild_id=guild_id, event_type="settings_updated",
                           details={"section": section, "actor_id": user["id"]}))
    await session.commit()
    logger.info("guild settings updated", extra={"guild_id": guild_id, "section": section})
    return result[section]


@router.get("/api/guilds/{guild_id}/analytics")
async def analytics(guild_id: int, request: Request, session: AsyncSession = Depends(get_db)):
    await require_guild_access(request, guild_id)
    since = datetime.now(timezone.utc) - timedelta(days=7)
    usage = (await session.execute(
        select(func.count(AIUsage.id), func.coalesce(func.sum(AIUsage.prompt_tokens), 0),
               func.coalesce(func.sum(AIUsage.completion_tokens), 0))
        .where(AIUsage.guild_id == guild_id, AIUsage.created_at >= since)
    )).one()
    cases = (await session.execute(
        select(func.count(ModerationCase.id)).where(
            ModerationCase.guild_id == guild_id, ModerationCase.created_at >= since
        )
    )).scalar_one()
    events = (await session.execute(
        select(GuildEvent.event_type, func.count(GuildEvent.id))
        .where(GuildEvent.guild_id == guild_id, GuildEvent.created_at >= since)
        .group_by(GuildEvent.event_type)
    )).all()
    day_counts = (await session.execute(
        select(func.date(AIUsage.created_at), func.count(AIUsage.id))
        .where(AIUsage.guild_id == guild_id, AIUsage.created_at >= since)
        .group_by(func.date(AIUsage.created_at)).order_by(func.date(AIUsage.created_at))
    )).all()
    return {
        "period_days": 7,
        "ai_requests": usage[0],
        "prompt_tokens": usage[1],
        "completion_tokens": usage[2],
        "moderation_cases": cases,
        "events": dict(events),
        "ai_by_day": [{"date": str(day), "requests": count} for day, count in day_counts],
    }


@router.get("/health")
async def health():
    return {"status": "ok"}
