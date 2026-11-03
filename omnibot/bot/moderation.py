import discord
from sqlalchemy.ext.asyncio import AsyncSession

from omnibot.db.models import ModerationCase


async def create_case(session: AsyncSession, guild_id: int, moderator_id: int,
                      target_id: int, action: str, reason: str) -> int:
    case = ModerationCase(guild_id=guild_id, moderator_id=moderator_id,
                          target_id=target_id, action=action, reason=reason[:500])
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case.id


def can_moderate(interaction: discord.Interaction, target: discord.Member) -> bool:
    actor = interaction.user
    guild = interaction.guild
    if not isinstance(actor, discord.Member) or guild is None or actor.id == target.id:
        return False
    if actor.id == guild.owner_id:
        return True
    return actor.top_role > target.top_role and target.id != guild.owner_id
