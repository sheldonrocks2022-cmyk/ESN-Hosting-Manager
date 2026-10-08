"""Honeypot audit monitoring and opt-in punishment with conservative attribution."""
import asyncio
import os
from datetime import datetime,timezone,timedelta
import discord
from discord import app_commands
from discord.ext import commands
from . import config

CHOICES=[
    app_commands.Choice(name="Alert only",value="alert"),
    app_commands.Choice(name="Timeout (1 hour)",value="timeout"),
    app_commands.Choice(name="Kick",value="kick"),
    app_commands.Choice(name="Ban",value="ban"),
]

class Security(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def alert(self,guild,kind,actor,detail):
        config.audit(guild.id,kind,actor,detail)
        channel=guild.get_channel(int(config.get(guild.id,"security_channel","0")))
        if isinstance(channel,discord.TextChannel):
            try:
                await channel.send(
                    f"🛡️ **{kind}** — actor `{actor}`\n{discord.utils.escape_mentions(detail)[:1500]}",
                    allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException: pass

    async def handle_audit(self,guild,action,target_id,kind,detail):
        if config.get(guild.id,"security_enabled")!="1" or config.get(guild.id,"honeypot_enabled")!="1": return
        await asyncio.sleep(1.5)
        try:
            async for entry in guild.audit_logs(limit=8,action=action):
                if not entry.target or entry.target.id!=target_id: continue
                if abs((datetime.now(timezone.utc)-entry.created_at).total_seconds())>15: continue
                actor=entry.user
                if not actor: break
                actor_id=actor.id
                if actor_id in (guild.owner_id,self.bot.user.id,int(os.getenv("OWNER_DISCORD_ID") or 0)):
                    await self.alert(guild,kind+"_EXEMPT",actor_id,detail+" (owner/bot exempt)")
                    return
                member=guild.get_member(actor_id)
                if member and (member.guild_permissions.administrator or config.role_allowed(member)):
                    await self.alert(guild,kind+"_STAFF",actor_id,detail+" (staff exempt)")
                    return
                mode=config.get(guild.id,"honeypot_mode","alert")
                if mode=="alert":
                    await self.alert(guild,kind,actor_id,detail+" (alert-only)")
                    return
                if not member or member.top_role>=guild.me.top_role:
                    await self.alert(guild,kind+"_NO_ACTION",actor_id,detail+" (actor unavailable or role hierarchy)")
                    return
                try:
                    reason="ESN honeypot: verified unauthorized decoy tampering"
                    if mode=="timeout": await member.timeout(timedelta(hours=1),reason=reason)
                    elif mode=="kick": await member.kick(reason=reason)
                    elif mode=="ban": await guild.ban(member,reason=reason,delete_message_seconds=0)
                    else: return
                    await self.alert(guild,kind+"_ENFORCED",actor_id,f"{detail} | action: {mode}")
                except (discord.Forbidden,discord.HTTPException) as exc:
                    await self.alert(guild,kind+"_FAILED",actor_id,f"{detail} | {mode} failed: {type(exc).__name__}")
                return
        except (discord.Forbidden,discord.HTTPException):
            await self.alert(guild,kind+"_AUDIT_UNAVAILABLE",0,detail+" (requires View Audit Log)")
            return
        await self.alert(guild,kind+"_UNATTRIBUTED",0,detail+" (no matching audit entry; no action)")

    @commands.Cog.listener()
    async def on_guild_channel_update(self,before,after):
        if str(after.id)!=config.get(after.guild.id,"honeypot_channel"): return
        if before.name!=after.name or before.overwrites!=after.overwrites:
            await self.handle_audit(after.guild,discord.AuditLogAction.channel_update,after.id,"HONEYPOT_CHANGED",f"Decoy channel {after.id} modified")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self,channel):
        if str(channel.id)==config.get(channel.guild.id,"honeypot_channel"):
            await self.handle_audit(channel.guild,discord.AuditLogAction.channel_delete,channel.id,"HONEYPOT_DELETED",f"Decoy channel {channel.id} deleted")
        elif config.get(channel.guild.id,"security_enabled")=="1":
            await self.alert(channel.guild,"CHANNEL_DELETED",0,f"Channel {channel.name} deleted; audit attribution not yet verified")

    @commands.Cog.listener()
    async def on_guild_role_delete(self,role):
        if config.get(role.guild.id,"security_enabled")=="1":
            await self.alert(role.guild,"ROLE_DELETED",0,f"Role {role.name} deleted; audit attribution not yet verified")

    @app_commands.command(name="security",description="Enable or disable security event monitoring")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def security(self,interaction:discord.Interaction,enabled:bool):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        config.put(interaction.guild.id,"security_enabled",int(enabled))
        await interaction.response.send_message(f"Security monitoring {'enabled' if enabled else 'disabled'}.",ephemeral=True)

    @app_commands.command(name="honeypot",description="Select a decoy channel and enable or disable the honeypot")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def honeypot(self,interaction:discord.Interaction,enabled:bool,decoy_channel:discord.TextChannel|None=None):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        if enabled and not (decoy_channel or config.get(interaction.guild.id,"honeypot_channel")):
            return await interaction.response.send_message("Choose a decoy channel.",ephemeral=True)
        if decoy_channel: config.put(interaction.guild.id,"honeypot_channel",decoy_channel.id)
        config.put(interaction.guild.id,"honeypot_enabled",int(enabled))
        await interaction.response.send_message(f"Honeypot {'enabled' if enabled else 'disabled'}. Mode: {config.get(interaction.guild.id,'honeypot_mode','alert')}.",ephemeral=True)

    @app_commands.command(name="honeypotmode",description="Choose alert timeout kick or ban for verified decoy tampering")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(mode=CHOICES)
    async def honeypotmode(self,interaction:discord.Interaction,mode:app_commands.Choice[str]):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        if mode.value!="alert" and not config.owner_allowed(interaction.user):
            return await interaction.response.send_message("Only the configured ESN owner may enable automatic punishment.",ephemeral=True)
        config.put(interaction.guild.id,"honeypot_mode",mode.value)
        await interaction.response.send_message(
            f"Honeypot mode: **{mode.value}**. Requires /security enabled, /honeypot enabled, View Audit Log, and appropriate moderation permissions. Owners, administrators and configured staff are exempt.",
            ephemeral=True)

    @app_commands.command(name="honeypotstatus",description="View honeypot configuration")
    @app_commands.guild_only()
    async def honeypotstatus(self,interaction:discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        guild=interaction.guild
        channel=guild.get_channel(int(config.get(guild.id,"honeypot_channel","0")))
        await interaction.response.send_message(
            f"**Honeypot**\nSecurity: {config.get(guild.id,'security_enabled','0')}\nEnabled: {config.get(guild.id,'honeypot_enabled','0')}\n"
            f"Channel: {channel.mention if channel else 'Not selected'}\nAction: {config.get(guild.id,'honeypot_mode','alert')}",
            ephemeral=True)

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
