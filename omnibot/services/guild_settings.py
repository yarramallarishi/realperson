from copy import deepcopy

from sqlalchemy.ext.asyncio import AsyncSession

from omnibot.db.models import GuildSettings

DEFAULT_SETTINGS = {
    "ai": {
        "enabled": False,
        "model": "llama-3.3-70b-versatile",
        "personality": "You are OmniBot, a helpful, concise, and friendly community assistant.",
        "cooldown_seconds": 8,
        "memory_messages": 8,
        "allowed_channels": [],
    },
    "automod": {
        "enabled": False,
        "invite_filter": False,
        "duplicate_filter": True,
        "mention_limit": 6,
        "caps_threshold": 0.8,
        "banned_words": [],
        "log_channel_id": None,
    },
    "welcome": {"enabled": False, "channel_id": None, "message": "Welcome {user} to {server}!"},
    "general": {"prefix": "!", "timezone": "UTC"},
}


async def get_guild_settings(session: AsyncSession, guild_id: int) -> dict:
    row = await session.get(GuildSettings, guild_id)
    if row is None:
        return deepcopy(DEFAULT_SETTINGS)
    return merge_defaults(row.settings)


def merge_defaults(value: dict) -> dict:
    result = deepcopy(DEFAULT_SETTINGS)
    for section, settings in value.items():
        if section in result and isinstance(settings, dict):
            result[section].update(settings)
    return result


async def save_guild_settings(session: AsyncSession, guild_id: int, patch: dict) -> dict:
    row = await session.get(GuildSettings, guild_id)
    current = merge_defaults(row.settings if row else {})
    for section, values in patch.items():
        current[section].update(values)
    if row is None:
        row = GuildSettings(guild_id=guild_id, settings=current)
        session.add(row)
    else:
        row.settings = current
    await session.commit()
    return current
