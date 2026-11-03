import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from omnibot.bot.moderation import can_moderate, create_case
from omnibot.db.models import ModerationCase
from omnibot.db.session import SessionLocal
from omnibot.services.guild_settings import get_guild_settings

logger = logging.getLogger(__name__)

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _case(self, interaction: discord.Interaction, target: discord.abc.Snowflake,
                    action: str, reason: str) -> int:
        async with SessionLocal() as session:
            case_id = await create_case(session, interaction.guild_id, interaction.user.id,
                                        target.id, action, reason)
            settings = (await get_guild_settings(session, interaction.guild_id))["automod"]
        log_channel_id = settings["log_channel_id"]
        guild = interaction.guild
        log_channel = guild.get_channel(int(log_channel_id)) if guild and log_channel_id else None
        if isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(title=f"Moderation case #{case_id}", color=discord.Color.blurple())
            embed.add_field(name="Action", value=action, inline=True)
            embed.add_field(name="Target", value=f"{target} (`{target.id}`)", inline=True)
            embed.add_field(name="Moderator", value=str(interaction.user), inline=True)
            embed.add_field(name="Reason", value=reason[:1000], inline=False)
            try:
                await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logger.warning("Could not post moderation log",
                               extra={"guild_id": interaction.guild_id, "case_id": case_id})
        return case_id

    @app_commands.command(description="Record a warning for a member")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not can_moderate(interaction, member):
            await interaction.response.send_message("You cannot moderate this member due to role hierarchy.", ephemeral=True)
            return
        case_id = await self._case(interaction, member, "warn", reason)
        await interaction.response.send_message(f"Warning recorded for {member.mention}. Case #{case_id}.")

    @app_commands.command(description="View a member's recent warning history")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        async with SessionLocal() as session:
            cases = (await session.execute(
                select(ModerationCase).where(
                    ModerationCase.guild_id == interaction.guild_id,
                    ModerationCase.target_id == member.id,
                    ModerationCase.action == "warn",
                ).order_by(ModerationCase.id.desc()).limit(10)
            )).scalars().all()
        if not cases:
            await interaction.response.send_message(f"{member.mention} has no recorded warnings.", ephemeral=True)
            return
        lines = [f"**Case #{case.id}** · <t:{int(case.created_at.timestamp())}:R> — {case.reason}"
                 for case in cases]
        await interaction.response.send_message(
            f"Recent warnings for {member.mention}:\n" + "\n".join(lines), ephemeral=True
        )

    @app_commands.command(description="Kick a member (requires explicit confirmation)")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member,
                   confirm: bool, reason: str = "No reason provided"):
        if not confirm:
            await interaction.response.send_message("Set `confirm` to true to proceed.", ephemeral=True)
            return
        if not can_moderate(interaction, member):
            await interaction.response.send_message("You cannot moderate this member due to role hierarchy.", ephemeral=True)
            return
        try:
            await member.kick(reason=f"{reason} | Moderator: {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("The bot lacks permission or role hierarchy to kick this member.", ephemeral=True)
            return
        case_id = await self._case(interaction, member, "kick", reason)
        await interaction.response.send_message(f"Kicked {member} (case #{case_id}).")

    @app_commands.command(description="Ban a member (requires explicit confirmation)")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  confirm: bool, reason: str = "No reason provided"):
        if not confirm:
            await interaction.response.send_message("Set `confirm` to true to proceed.", ephemeral=True)
            return
        if not can_moderate(interaction, member):
            await interaction.response.send_message("You cannot moderate this member due to role hierarchy.", ephemeral=True)
            return
        try:
            await member.ban(reason=f"{reason} | Moderator: {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("The bot lacks permission or role hierarchy to ban this member.", ephemeral=True)
            return
        case_id = await self._case(interaction, member, "ban", reason)
        await interaction.response.send_message(f"Banned {member} (case #{case_id}).")

    @app_commands.command(description="Unban a user by ID (requires explicit confirmation)")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, confirm: bool,
                    reason: str = "No reason provided"):
        if not confirm:
            await interaction.response.send_message("Set `confirm` to true to proceed.", ephemeral=True)
            return
        if not user_id.isdigit():
            await interaction.response.send_message("Enter a valid Discord user ID.", ephemeral=True)
            return
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{reason} | Moderator: {interaction.user}")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Could not unban that user. Check the ID and bot permissions.", ephemeral=True)
            return
        case_id = await self._case(interaction, user, "unban", reason)
        await interaction.response.send_message(f"Unbanned {user} (case #{case_id}).")

    @app_commands.command(description="Timeout a member")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                      minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
        if not can_moderate(interaction, member):
            await interaction.response.send_message("You cannot moderate this member due to role hierarchy.", ephemeral=True)
            return
        try:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("The bot lacks permission or role hierarchy to timeout this member.", ephemeral=True)
            return
        case_id = await self._case(interaction, member, "timeout", reason)
        await interaction.response.send_message(f"Timed out {member.mention} (case #{case_id}).")

    @app_commands.command(description="Delete recent messages (requires explicit confirmation)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction,
                    amount: app_commands.Range[int, 1, 100], confirm: bool):
        if not confirm:
            await interaction.response.send_message("Set `confirm` to true to proceed.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Purge is only available in text channels.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        case_id = await self._case(interaction, interaction.user, "purge", f"Deleted {len(deleted)} messages")
        await interaction.followup.send(f"Deleted {len(deleted)} messages (case #{case_id}).")

    @app_commands.command(description="Set a channel slowmode")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command requires a text channel.", ephemeral=True)
            return
        await interaction.channel.edit(slowmode_delay=seconds, reason=f"Set by {interaction.user}")
        case_id = await self._case(interaction, interaction.channel, "slowmode", f"Set to {seconds} seconds")
        await interaction.response.send_message(f"Slowmode set to {seconds} seconds (case #{case_id}).")

    @app_commands.command(description="Lock this text channel")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("This command requires a text channel.", ephemeral=True)
            return
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite,
                                      reason=f"Locked by {interaction.user}")
        case_id = await self._case(interaction, channel, "lock", f"Locked #{channel.name}")
        await interaction.response.send_message(f"Channel locked (case #{case_id}).")

    @app_commands.command(description="Unlock this text channel")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("This command requires a text channel.", ephemeral=True)
            return
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite,
                                      reason=f"Unlocked by {interaction.user}")
        case_id = await self._case(interaction, channel, "unlock", f"Unlocked #{channel.name}")
        await interaction.response.send_message(f"Channel unlocked (case #{case_id}).")


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
