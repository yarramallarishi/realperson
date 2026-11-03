from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]

    @field_validator("values")
    @classmethod
    def nonempty_patch(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values:
            raise ValueError("At least one setting is required")
        return values


AI_KEYS = {"enabled", "model", "personality", "cooldown_seconds", "memory_messages", "allowed_channels"}
AUTOMOD_KEYS = {"enabled", "invite_filter", "duplicate_filter", "mention_limit",
                "caps_threshold", "banned_words", "log_channel_id"}
WELCOME_KEYS = {"enabled", "channel_id", "message"}
GENERAL_KEYS = {"prefix", "timezone"}


def validate_section(section: str, values: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "ai": AI_KEYS, "automod": AUTOMOD_KEYS, "welcome": WELCOME_KEYS, "general": GENERAL_KEYS
    }.get(section)
    if allowed is None:
        raise ValueError("Unknown settings section")
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
    boolean_keys = {"enabled", "invite_filter", "duplicate_filter"}
    for key in boolean_keys.intersection(values):
        if type(values[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    string_keys = {"model", "personality", "message", "prefix", "timezone"}
    for key in string_keys.intersection(values):
        if not isinstance(values[key], str):
            raise ValueError(f"{key} must be a string")
    for key in {"cooldown_seconds", "memory_messages", "mention_limit"}.intersection(values):
        if type(values[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    if "caps_threshold" in values and (type(values["caps_threshold"]) not in (int, float)):
        raise ValueError("caps_threshold must be a number")
    if "cooldown_seconds" in values and not 1 <= values["cooldown_seconds"] <= 120:
        raise ValueError("cooldown_seconds must be between 1 and 120")
    if "memory_messages" in values and not 0 <= values["memory_messages"] <= 20:
        raise ValueError("memory_messages must be between 0 and 20")
    if "mention_limit" in values and not 1 <= values["mention_limit"] <= 20:
        raise ValueError("mention_limit must be between 1 and 20")
    if "caps_threshold" in values and not 0.5 <= values["caps_threshold"] <= 1:
        raise ValueError("caps_threshold must be between 0.5 and 1")
    if "personality" in values and len(values["personality"]) > 1200:
        raise ValueError("personality must be at most 1200 characters")
    if "model" in values and values["model"] not in {
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b"
    }:
        raise ValueError("model is not supported")
    if "message" in values and len(values["message"]) > 1000:
        raise ValueError("welcome message must be at most 1000 characters")
    if "prefix" in values and not 1 <= len(values["prefix"]) <= 3:
        raise ValueError("prefix must contain between 1 and 3 characters")
    if "timezone" in values:
        try:
            ZoneInfo(values["timezone"])
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
    if "banned_words" in values:
        words = values["banned_words"]
        if not isinstance(words, list) or len(words) > 100 or any(
            not isinstance(word, str) or not word.strip() or len(word) > 60 for word in words
        ):
            raise ValueError("banned_words must contain at most 100 non-empty words")
    if "allowed_channels" in values:
        channels = values["allowed_channels"]
        if not isinstance(channels, list) or len(channels) > 100 or any(
            not str(channel).isdigit() for channel in channels
        ):
            raise ValueError("allowed_channels must contain at most 100 channel IDs")
    for key in ("channel_id", "log_channel_id"):
        if key in values and values[key] is not None:
            if not isinstance(values[key], (str, int)) or not str(values[key]).isdigit() or len(str(values[key])) > 20:
                raise ValueError(f"{key} must be a Discord channel ID or null")
    return values
