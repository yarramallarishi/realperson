import logging

import discord
from discord.ext import commands

from omnibot.config import get_settings
from omnibot.db.session import init_db
from omnibot.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class OmniBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        await init_db()
        await self.load_extension("omnibot.bot.cogs.ai")
        await self.load_extension("omnibot.bot.cogs.moderation")
        await self.load_extension("omnibot.bot.cogs.community")
        await self.tree.sync()

    async def on_ready(self) -> None:
        logger.info("Discord bot connected", extra={"user_id": self.user.id if self.user else None})

    async def on_message(self, message: discord.Message) -> None:
        if message.guild and not message.author.bot:
            from omnibot.bot.automod import check_message
            from omnibot.db.session import SessionLocal
            async with SessionLocal() as session:
                try:
                    reason = await check_message(message, session)
                except discord.Forbidden:
                    logger.warning("Automod could not delete message", extra={"guild_id": message.guild.id})
                    reason = None
            if reason:
                try:
                    await message.channel.send(f"{message.author.mention}, message removed: {reason}.",
                                               delete_after=6)
                except discord.HTTPException:
                    logger.warning("Could not post automod notice", extra={"guild_id": message.guild.id})
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member) -> None:
        from omnibot.bot.automod import record_join
        from omnibot.db.session import SessionLocal
        async with SessionLocal() as session:
            suspected = await record_join(member.guild, member, session)
        if suspected:
            logger.warning("Possible raid detected", extra={"guild_id": member.guild.id})


def run() -> None:
    token = get_settings().discord_token
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not configured")
    bot = OmniBot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    run()
