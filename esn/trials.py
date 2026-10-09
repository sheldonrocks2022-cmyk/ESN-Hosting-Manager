from .luxury import luxury_send, luxury_followup
"""One trial per Discord user, approval handled by staff."""
from datetime import datetime,timedelta,timezone
import discord
from discord import app_commands
from discord.ext import commands
from . import config

class Trials(commands.Cog):
    def __init__(self,bot): self.bot=bot

    @app_commands.command(name="trialrequest",description="Request your one-time 14-day hosting trial")
    @app_commands.guild_only()
    async def trialrequest(self,interaction:discord.Interaction):
        guild=interaction.guild.id
        row=config.db.execute("SELECT status FROM trials WHERE user=?",(interaction.user.id,)).fetchone()
        if row: return await luxury_send(interaction, f"Trial already recorded: {row[0]}. Contact support.",ephemeral=True)
        config.db.execute("INSERT INTO trials(user,guild,expires_at,status) VALUES(?,?,?,?)",(interaction.user.id,guild,None,"pending"))
        config.db.commit()
        await luxury_send(interaction, "Trial request recorded. Staff must approve it before a server is provisioned.",ephemeral=True)

    @app_commands.command(name="trialapprove",description="Approve a pending trial; does not provision a server")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def trialapprove(self,interaction:discord.Interaction,member:discord.Member):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction, "Manage Server required.",ephemeral=True)
        row=config.db.execute("SELECT status FROM trials WHERE user=? AND guild=?",(member.id,interaction.guild.id)).fetchone()
        if not row or row[0]!="pending":
            return await luxury_send(interaction, "No pending trial for that member.",ephemeral=True)
        expiry=(datetime.now(timezone.utc)+timedelta(days=14)).isoformat()
        config.db.execute("UPDATE trials SET status='approved', expires_at=? WHERE user=?",(expiry,member.id))
        config.db.commit()
        await luxury_send(interaction, f"Approved {member.mention}'s 14-day trial until {expiry}. Provisioning is a separate step.",ephemeral=True)

    @app_commands.command(name="trialstatus",description="Check your hosting trial status")
    @app_commands.guild_only()
    async def trialstatus(self,interaction:discord.Interaction):
        row=config.db.execute("SELECT status,expires_at FROM trials WHERE user=?",(interaction.user.id,)).fetchone()
        await luxury_send(interaction, f"Trial: **{row[0]}**; expires: {row[1] or 'Not started'}" if row else "No trial request found.",ephemeral=True)

async def setup(bot): await bot.add_cog(Trials(bot))
