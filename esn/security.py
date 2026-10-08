"""Conservative security monitoring: alerts only, no automatic bans or destructive actions."""
import discord
from discord import app_commands
from discord.ext import commands
from . import config

class Security(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def alert(self,guild,kind,actor,detail):
        config.audit(guild.id,kind,actor,detail)
        channel=guild.get_channel(int(config.get(guild.id,"security_channel","0")))
        if isinstance(channel,discord.TextChannel):
            try:
                await channel.send(f"🛡️ **{kind}** — actor `{actor}`\n{discord.utils.escape_mentions(detail)[:1500]}",allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException: pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self,channel):
        if config.get(channel.guild.id,"security_enabled")!="1": return
        await self.alert(channel.guild,"CHANNEL_DELETED",0,f"Channel {channel.name} was deleted. Check Discord audit logs for attribution.")

    @commands.Cog.listener()
    async def on_guild_role_delete(self,role):
        if config.get(role.guild.id,"security_enabled")!="1": return
        await self.alert(role.guild,"ROLE_DELETED",0,f"Role {role.name} was deleted. Check Discord audit logs for attribution.")

    @commands.Cog.listener()
    async def on_guild_channel_update(self,before,after):
        guild=after.guild
        if config.get(guild.id,"honeypot_enabled")!="1": return
        if str(after.id)!=config.get(guild.id,"honeypot_channel"): return
        if before.overwrites!=after.overwrites or before.name!=after.name:
            await self.alert(guild,"HONEYPOT_CHANNEL_CHANGED",0,f"Decoy channel {after.id} changed. Review audit logs before acting.")

    @app_commands.command(name="security",description="Configure alert-only security monitoring")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def security(self,interaction:discord.Interaction, enabled:bool):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        config.put(interaction.guild.id,"security_enabled",int(enabled))
        await interaction.response.send_message(f"Security alerts {'enabled' if enabled else 'disabled'}. No automatic punishment.",ephemeral=True)

    @app_commands.command(name="honeypot",description="Configure a decoy channel monitoring trap")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def honeypot(self,interaction:discord.Interaction, enabled:bool, decoy_channel:discord.TextChannel|None=None):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        if enabled and not (decoy_channel or config.get(interaction.guild.id,"honeypot_channel")):
            return await interaction.response.send_message("Select a decoy channel first.",ephemeral=True)
        if decoy_channel: config.put(interaction.guild.id,"honeypot_channel",decoy_channel.id)
        config.put(interaction.guild.id,"honeypot_enabled",int(enabled))
        await interaction.response.send_message("Honeypot monitoring updated. This watches decoy channel changes; it does not automatically punish users.",ephemeral=True)

    @app_commands.command(name="securitylogs",description="Show recent security incidents")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def securitylogs(self,interaction:discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        rows=config.db.execute("SELECT created_at,kind,detail FROM incidents WHERE guild=? ORDER BY id DESC LIMIT 8",(interaction.guild.id,)).fetchall()
        lines=[f"`{date}` **{kind}** {detail[:80]}" for date,kind,detail in rows]
        await interaction.response.send_message("\n".join(lines)[:1900] if lines else "No incidents recorded.",ephemeral=True)

async def setup(bot): await bot.add_cog(Security(bot))
