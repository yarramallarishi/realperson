import base64
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from time import monotonic

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, status

from omnibot.config import get_settings
from omnibot.db.models import AuthSession
from omnibot.db.session import SessionLocal

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 1 << 5
GUILD_CACHE_TTL_SECONDS = 30
_guild_cache: dict[str, tuple[float, list[dict]]] = {}
_guild_cache_locks: dict[str, asyncio.Lock] = {}


def clear_guild_cache(session_id: str | None) -> None:
    if session_id:
        _guild_cache.pop(session_id, None)
        _guild_cache_locks.pop(session_id, None)


def _discord_error(response: httpx.Response) -> HTTPException:
    if response.status_code == 429:
        try:
            retry_after = max(1, int(float(response.headers.get("Retry-After", "5")) + 0.999))
        except ValueError:
            retry_after = 5
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord is temporarily rate-limiting server access checks. Please try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
    return HTTPException(status_code=502, detail="Discord API request failed")


def encrypt_access_token(token: str) -> str:
    secret = get_settings().session_secret.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret + b":omnibot-oauth").digest())
    return Fernet(key).encrypt(token.encode()).decode()


def decrypt_access_token(token: str) -> str:
    secret = get_settings().session_secret.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret + b":omnibot-oauth").digest())
    try:
        return Fernet(key).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(status_code=401, detail="Discord session is invalid; sign in again") from exc


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://discord.com/api/v10/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Discord OAuth token exchange failed")
    return response.json()


async def discord_get(path: str, token: str) -> list | dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{DISCORD_API}{path}", headers={"Authorization": f"Bearer {token}"}
        )
    if response.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Discord session expired")
    if response.is_error:
        raise _discord_error(response)
    return response.json()


async def load_login(request: Request) -> tuple[dict, str]:
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in with Discord")
    async with SessionLocal() as db:
        record = await db.get(AuthSession, session_id)
        if record is None:
            request.session.clear()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in with Discord")
        expiry = record.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            await db.delete(record)
            await db.commit()
            request.session.clear()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Discord session expired")
        user = record.user
        token = decrypt_access_token(record.encrypted_access_token)
    return user, token


async def require_user(request: Request) -> dict:
    user, _ = await load_login(request)
    return user


async def authorized_guilds(request: Request) -> list[dict]:
    _, token = await load_login(request)
    session_id = request.session["session_id"]
    now = monotonic()
    cached = _guild_cache.get(session_id)
    if cached and now - cached[0] < GUILD_CACHE_TTL_SECONDS:
        return cached[1]

    lock = _guild_cache_locks.setdefault(session_id, asyncio.Lock())
    async with lock:
        now = monotonic()
        cached = _guild_cache.get(session_id)
        if cached and now - cached[0] < GUILD_CACHE_TTL_SECONDS:
            return cached[1]
        guilds = await discord_get("/users/@me/guilds", token)
        manageable = [
            guild for guild in guilds
            if guild.get("owner") or int(guild.get("permissions", "0")) & MANAGE_GUILD
        ]
        _guild_cache[session_id] = (monotonic(), manageable)
        if len(_guild_cache) > 1024:
            cutoff = monotonic() - GUILD_CACHE_TTL_SECONDS
            for key, (cached_at, _) in list(_guild_cache.items()):
                if cached_at < cutoff:
                    _guild_cache.pop(key, None)
                    _guild_cache_locks.pop(key, None)
        return manageable


async def require_guild_access(request: Request, guild_id: int) -> dict:
    guild = next((item for item in await authorized_guilds(request)
                  if int(item["id"]) == guild_id), None)
    if guild is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Manage Server permission is required for this server")
    return guild
