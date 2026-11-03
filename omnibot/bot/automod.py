import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from omnibot.db.models import GuildEvent
from omnibot.services.guild_settings import get_guild_settings

logger = logging.getLogger(__name__)
INVITE_PATTERN = re.compile(r"(?:discord\.gg/|discord(?:app)?\.com/invite/)[\w-]+", re.I)
recent_messages: dict[tuple[int, int], deque[tuple[datetime, str]]] = defaultdict(deque)
join_times: dict[int, deque[datetime]] = defaultdict(deque)


async def check_message(message: discord.Message, session: AsyncSession) -> str | None:
    if not message.guild or message.author.bot:
        return None
    config = (await get_guild_settings(session, message.guild.id))["automod"]
    if not config["enabled"]:
        return None
    content = message.content
    reason = None
    if config["invite_filter"] and INVITE_PATTERN.search(content):
        reason = "invite link"
    elif len(message.mentions) > config["mention_limit"]:
        reason = "mention spam"
    elif any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", content, re.IGNORECASE)
             for word in config["banned_words"]):
        reason = "banned word"
    elif config["duplicate_filter"]:
        key = (message.guild.id, message.author.id)
        now = datetime.now(timezone.utc)
        recent = recent_messages[key]
        while recent and now - recent[0][0] > timedelta(seconds=12):
            recent.popleft()
        if any(previous == content.casefold() for _, previous in recent):
            reason = "duplicate message"
        recent.append((now, content.casefold()))
    if not reason and len(content) >= 12:
        letters = [char for char in content if char.isalpha()]
        if len(letters) >= 10 and sum(char.isupper() for char in letters) / len(letters) >= config["caps_threshold"]:
            reason = "excessive caps"
    if reason:
        if message.guild.me and message.guild.me.guild_permissions.manage_messages:
            await message.delete()
        session.add(GuildEvent(guild_id=message.guild.id, event_type="automod",
                               details={"user_id": str(message.author.id), "reason": reason}))
        await session.commit()
        log_channel_id = config["log_channel_id"]
        log_channel = message.guild.get_channel(int(log_channel_id)) if log_channel_id else None
        if isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(title="Auto moderation", color=discord.Color.orange())
            embed.add_field(name="Member", value=f"{message.author} (`{message.author.id}`)", inline=False)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            try:
                await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logger.warning("Could not post automod log", extra={"guild_id": message.guild.id})
        return reason
    return None


async def record_join(guild: discord.Guild, member: discord.Member, session: AsyncSession) -> bool:
    now = datetime.now(timezone.utc)
    times = join_times[guild.id]
    while times and now - times[0] > timedelta(seconds=20):
        times.popleft()
    times.append(now)
    raid_suspected = len(times) >= 8
    session.add(GuildEvent(guild_id=guild.id, event_type="member_join",
                           details={"user_id": str(member.id), "raid_suspected": raid_suspected}))
    await session.commit()
    return raid_suspected
