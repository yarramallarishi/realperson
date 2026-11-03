import logging
import time

import discord
from discord import app_commands
from discord.ext import commands
from groq import APIError
from sqlalchemy import delete, select

from omnibot.ai.groq_provider import GroqProvider
from omnibot.db.models import AIUsage, ConversationMessage
from omnibot.db.session import SessionLocal
from omnibot.services.guild_settings import get_guild_settings

logger = logging.getLogger(__name__)
last_request: dict[tuple[int, int], float] = {}
last_cooldown_prune = 0.0


def consume_cooldown(key: tuple[int, int], cooldown_seconds: int) -> float:
    global last_cooldown_prune
    now = time.monotonic()
    previous = last_request.get(key)
    if previous is not None and now - previous < cooldown_seconds:
        return cooldown_seconds - (now - previous)
    last_request[key] = now
    if now - last_cooldown_prune >= 60:
        stale_before = now - 600
        for stale_key, timestamp in list(last_request.items()):
            if timestamp < stale_before:
                del last_request[stale_key]
        last_cooldown_prune = now
    return 0.0


class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ask", description="Ask OmniBot a question")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        key = (interaction.guild.id, interaction.user.id)
        async with SessionLocal() as session:
            config = (await get_guild_settings(session, interaction.guild.id))["ai"]
            if not config["enabled"]:
                await interaction.response.send_message("AI chat is disabled for this server.", ephemeral=True)
                return
            if config["allowed_channels"] and str(interaction.channel_id) not in config["allowed_channels"]:
                await interaction.response.send_message("AI chat is not enabled in this channel.", ephemeral=True)
                return
            if len(question) > 1500:
                await interaction.response.send_message("Keep questions under 1,500 characters.", ephemeral=True)
                return
            remaining = consume_cooldown(key, config["cooldown_seconds"])
            if remaining > 0:
                await interaction.response.send_message(
                    f"Please wait {remaining:.0f} seconds before asking again.", ephemeral=True
                )
                return

            await interaction.response.defer(thinking=True)
            history = (await session.execute(
                select(ConversationMessage).where(
                    ConversationMessage.guild_id == interaction.guild.id,
                    ConversationMessage.channel_id == interaction.channel_id,
                    ConversationMessage.user_id == interaction.user.id,
                ).order_by(ConversationMessage.id.desc()).limit(config["memory_messages"])
            )).scalars().all()
            messages = [{"role": "system", "content": config["personality"]}]
            messages.extend({"role": row.role, "content": row.content} for row in reversed(history))
            messages.append({"role": "user", "content": question})
            try:
                result = await GroqProvider().complete(config["model"], messages)
            except RuntimeError as exc:
                logger.error("AI provider is not configured", extra={
                    "guild_id": interaction.guild.id, "error_type": type(exc).__name__,
                })
                await interaction.followup.send("AI is not configured yet. Ask a server manager for help.")
                return
            except APIError as exc:
                logger.warning("AI provider request failed", extra={
                    "guild_id": interaction.guild.id, "error_type": type(exc).__name__,
                })
                await interaction.followup.send("AI is temporarily unavailable. Please try again later.")
                return
            session.add_all([
                ConversationMessage(guild_id=interaction.guild.id, channel_id=interaction.channel_id,
                                    user_id=interaction.user.id, role="user", content=question[:1500]),
                ConversationMessage(guild_id=interaction.guild.id, channel_id=interaction.channel_id,
                                    user_id=interaction.user.id, role="assistant", content=result.content[:1900]),
                AIUsage(guild_id=interaction.guild.id, user_id=interaction.user.id,
                        prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens),
            ])
            await session.commit()
        await interaction.followup.send(
            (result.content or "I couldn't generate a response.")[:1900],
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="resetchat", description="Clear your saved AI conversation in this channel")
    async def resetchat(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        async with SessionLocal() as session:
            await session.execute(delete(ConversationMessage).where(
                ConversationMessage.guild_id == interaction.guild.id,
                ConversationMessage.channel_id == interaction.channel_id,
                ConversationMessage.user_id == interaction.user.id,
            ))
            await session.commit()
        await interaction.response.send_message("Your conversation memory was cleared.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or self.bot.user not in message.mentions or message.author.bot:
            return
        prompt = message.content.replace(f"<@{self.bot.user.id}>", "").replace(
            f"<@!{self.bot.user.id}>", ""
        ).strip()
        if not prompt:
            return
        channel = message.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        async with SessionLocal() as session:
            config = (await get_guild_settings(session, message.guild.id))["ai"]
            if not config["enabled"] or (config["allowed_channels"] and str(channel.id) not in config["allowed_channels"]):
                return
            key = (message.guild.id, message.author.id)
            remaining = consume_cooldown(key, config["cooldown_seconds"])
            if remaining > 0:
                return
            history = (await session.execute(
                select(ConversationMessage).where(
                    ConversationMessage.guild_id == message.guild.id,
                    ConversationMessage.channel_id == channel.id,
                    ConversationMessage.user_id == message.author.id,
                ).order_by(ConversationMessage.id.desc()).limit(config["memory_messages"])
            )).scalars().all()
            messages = [{"role": "system", "content": config["personality"]}]
            messages.extend({"role": row.role, "content": row.content} for row in reversed(history))
            messages.append({"role": "user", "content": prompt[:1500]})
            try:
                result = await GroqProvider().complete(config["model"], messages)
            except RuntimeError as exc:
                logger.error("AI provider is not configured", extra={
                    "guild_id": message.guild.id, "error_type": type(exc).__name__,
                })
                return
            except APIError as exc:
                logger.warning("Mention AI request failed", extra={
                    "guild_id": message.guild.id, "error_type": type(exc).__name__,
                })
                return
            session.add_all([
                ConversationMessage(guild_id=message.guild.id, channel_id=channel.id,
                                    user_id=message.author.id, role="user", content=prompt[:1500]),
                ConversationMessage(guild_id=message.guild.id, channel_id=channel.id,
                                    user_id=message.author.id, role="assistant", content=result.content[:1900]),
                AIUsage(guild_id=message.guild.id, user_id=message.author.id,
                        prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens),
            ])
            await session.commit()
        await message.reply(
            result.content[:1900],
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AICog(bot))
