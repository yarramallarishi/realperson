import pytest

from omnibot.api.schemas import validate_section
from omnibot.services import discord_auth
from omnibot.services.discord_auth import MANAGE_GUILD, decrypt_access_token, encrypt_access_token
from omnibot.services.rate_limit import SlidingWindowLimiter
from omnibot.services.guild_settings import DEFAULT_SETTINGS, merge_defaults


def test_manage_server_bit_is_discord_manage_guild():
    assert MANAGE_GUILD == 1 << 5


def test_guild_settings_merge_without_mutating_defaults():
    merged = merge_defaults({"ai": {"enabled": True}})
    assert merged["ai"]["enabled"] is True
    assert merged["automod"]["enabled"] is False
    assert DEFAULT_SETTINGS["ai"]["enabled"] is False


def test_settings_reject_unknown_fields():
    with pytest.raises(ValueError, match="Unknown settings"):
        validate_section("ai", {"secret": "not-allowed"})


def test_settings_enforce_cooldown_bounds():
    with pytest.raises(ValueError, match="between 1 and 120"):
        validate_section("ai", {"cooldown_seconds": 0})


def test_settings_reject_unknown_sections():
    with pytest.raises(ValueError, match="Unknown settings section"):
        validate_section("dangerous", {"enabled": True})


def test_oauth_access_tokens_are_encrypted_before_persistence():
    token = "discord-access-token-value"
    encrypted = encrypt_access_token(token)
    assert encrypted != token
    assert token not in encrypted
    assert decrypt_access_token(encrypted) == token


def test_settings_reject_wrong_input_types():
    with pytest.raises(ValueError, match="enabled must be a boolean"):
        validate_section("ai", {"enabled": "true"})


def test_rate_limiter_rejects_excess_and_expires_old_hits():
    limiter = SlidingWindowLimiter()
    assert limiter.hit("user", limit=2, window_seconds=10, now=100) is None
    assert limiter.hit("user", limit=2, window_seconds=10, now=101) is None
    assert limiter.hit("user", limit=2, window_seconds=10, now=102) == 8
    assert limiter.hit("user", limit=2, window_seconds=10, now=110) is None


@pytest.mark.asyncio
async def test_manageable_guilds_are_cached_per_login_session(monkeypatch):
    session_id = "guild-cache-test"
    discord_auth.clear_guild_cache(session_id)
    calls = 0

    async def fake_load_login(_request):
        return {"id": "user-1"}, "access-token"

    async def fake_discord_get(path, token):
        nonlocal calls
        calls += 1
        assert path == "/users/@me/guilds"
        assert token == "access-token"
        return [
            {"id": "managed", "owner": False, "permissions": str(MANAGE_GUILD)},
            {"id": "not-managed", "owner": False, "permissions": "0"},
            {"id": "owned", "owner": True, "permissions": "0"},
        ]

    monkeypatch.setattr(discord_auth, "load_login", fake_load_login)
    monkeypatch.setattr(discord_auth, "discord_get", fake_discord_get)
    request = type("Request", (), {"session": {"session_id": session_id}})()

    first = await discord_auth.authorized_guilds(request)
    second = await discord_auth.authorized_guilds(request)

    assert [guild["id"] for guild in first] == ["managed", "owned"]
    assert second == first
    assert calls == 1
    discord_auth.clear_guild_cache(session_id)
