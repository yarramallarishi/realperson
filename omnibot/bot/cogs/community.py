import discord
from discord import app_commands
from discord.ext import commands

from omnibot.db.session import SessionLocal
from omnibot.services.guild_settings import get_guild_settings


class CommunityCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Show information about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
        embed.add_field(name="Members", value=str(guild.member_count or "Unknown"))
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "D"))
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Create a simple poll")
    @app_commands.describe(question="Poll question", option_one="First option", option_two="Second option")
    async def poll(self, interaction: discord.Interaction, question: str, option_one: str, option_two: str):
        if len(question) > 250 or len(option_one) > 80 or len(option_two) > 80:
            await interaction.response.send_message("Question/options exceed the allowed length.", ephemeral=True)
            return
        embed = discord.Embed(title=question, color=discord.Color.blurple())
        embed.description = f"1️⃣ {option_one}\n2️⃣ {option_two}"
        await interaction.response.send_message(embed=embed)
        poll_message = await interaction.original_response()
        await poll_message.add_reaction("1️⃣")
        await poll_message.add_reaction("2️⃣")


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with SessionLocal() as session:
            if member.guild is None:
                return
            settings = (await get_guild_settings(session, member.guild.id))["welcome"]
            channel_id = int(settings["channel_id"]) if settings["channel_id"] else None
            channel = member.guild.get_channel(channel_id) if channel_id else None
            if settings["enabled"] and isinstance(channel, discord.TextChannel):
                content = settings["message"].replace("{user}", member.mention).replace(
                    "{server}", member.guild.name
                )
                await channel.send(
                    content[:1800],
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        async with SessionLocal() as session:
            settings = (await get_guild_settings(session, member.guild.id))["welcome"]
            channel_id = int(settings["channel_id"]) if settings["channel_id"] else None
            channel = member.guild.get_channel(channel_id) if channel_id else None
            if settings["enabled"] and isinstance(channel, discord.TextChannel):
                await channel.send(f"{member} left **{member.guild.name}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCog(bot))
    await bot.add_cog(WelcomeCog(bot))
