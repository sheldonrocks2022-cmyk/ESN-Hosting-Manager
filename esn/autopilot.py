"""Opt-in read-only ESN panel availability monitoring."""
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from . import config
from .luxury import luxury_send
from .operations import request
from partner_permissions import require_owner

class Autopilot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitor.start()

    def cog_unload(self):
        self.monitor.cancel()

    @app_commands.command(name="autopilot", description="Owner: toggle safe panel monitoring alerts")
    @app_commands.guild_only()
    async def autopilot(self, interaction: discord.Interaction, enabled: bool):
        try:
            require_owner(interaction.user.id)
        except PermissionError:
            return await luxury_send(interaction, "Owner only.", ephemeral=True)
        config.put(interaction.guild.id, "autopilot_enabled", int(enabled))
        await luxury_send(interaction, "Autopilot alerts " + ("enabled." if enabled else "disabled.") + " No automated billing or server power changes.", ephemeral=True)

    @tasks.loop(minutes=15)
    async def monitor(self):
        for guild in self.bot.guilds:
            if config.get(guild.id, "autopilot_enabled", "0") != "1":
                continue
            try:
                await request("GET", "/api/client")
                if config.get(guild.id, "autopilot_failed", "0") == "1":
                    config.put(guild.id, "autopilot_failed", "0")
                    await self.alert(guild, "Panel API connectivity restored.")
                config.put(guild.id, "autopilot_count", 0)
            except (RuntimeError, aiohttp.ClientError, TimeoutError):
                count = int(config.get(guild.id, "autopilot_count", "0")) + 1
                config.put(guild.id, "autopilot_count", count)
                if count >= 2 and config.get(guild.id, "autopilot_failed", "0") != "1":
                    config.put(guild.id, "autopilot_failed", "1")
                    await self.alert(guild, "Panel API failed two consecutive checks. Check panel status and API permissions.")

    async def alert(self, guild, message):
        config.audit(guild.id, "autopilot_alert", self.bot.user.id if self.bot.user else 0, message)
        channel = guild.get_channel(int(config.get(guild.id, "status_channel", "0")))
        if not isinstance(channel, discord.TextChannel):
            return
        icon = guild.icon.url if guild.icon else None
        embed = discord.Embed(title="ESN HOSTING | AUTOPILOT", description=message, color=0xD5AD65)
        if icon:
            embed.set_thumbnail(url=icon)
            embed.set_footer(text="ESN Hosting Monitoring", icon_url=icon)
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

    @monitor.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Autopilot(bot))
