"""Customer-facing plans, referrals and manual billing records. No fake payment verification."""
from datetime import datetime,timezone
import discord
from discord import app_commands
from discord.ext import commands
from . import config

config.db.execute("CREATE TABLE IF NOT EXISTS referrals (referred INTEGER PRIMARY KEY, referrer INTEGER, guild INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
config.db.execute("CREATE TABLE IF NOT EXISTS billing_notes (id INTEGER PRIMARY KEY, guild INTEGER, user INTEGER, note TEXT, actor INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
config.db.commit()

class Commerce(commands.Cog):
    def __init__(self,bot): self.bot=bot

    @app_commands.command(name="plans",description="View ESN Hosting plans")
    @app_commands.guild_only()
    async def plans(self,interaction:discord.Interaction):
        await interaction.response.send_message(
            "**ESN Hosting**\n"
            "Use the official ESN Hosting sales channel for current prices and availability.\n"
            "Ask staff for a 14-day trial with /trialrequest. No purchase is processed by this command.",
            ephemeral=True)

    @app_commands.command(name="refer",description="Record who referred you to ESN Hosting")
    @app_commands.guild_only()
    async def refer(self,interaction:discord.Interaction,referrer:discord.Member):
        if referrer.id==interaction.user.id or referrer.bot:
            return await interaction.response.send_message("Choose another real member.",ephemeral=True)
        existing=config.db.execute("SELECT referrer FROM referrals WHERE referred=?",(interaction.user.id,)).fetchone()
        if existing: return await interaction.response.send_message("You already recorded a referrer.",ephemeral=True)
        config.db.execute("INSERT INTO referrals(referred,referrer,guild) VALUES(?,?,?)",(interaction.user.id,referrer.id,interaction.guild.id))
        config.db.commit()
        await interaction.response.send_message("Referral recorded. Rewards require staff verification.",ephemeral=True)

    @app_commands.command(name="referrals",description="View your recorded referrals")
    @app_commands.guild_only()
    async def referrals(self,interaction:discord.Interaction):
        count=config.db.execute("SELECT COUNT(*) FROM referrals WHERE guild=? AND referrer=?",(interaction.guild.id,interaction.user.id)).fetchone()[0]
        await interaction.response.send_message(f"Recorded referrals: **{count}**. Rewards are not automatic.",ephemeral=True)

    @app_commands.command(name="billingnote",description="Record an internal order note; does not verify payment")
    @app_commands.guild_only()
    async def billingnote(self,interaction:discord.Interaction,customer:discord.Member,note:str):
        if not config.owner_allowed(interaction.user):
            return await interaction.response.send_message("Only the configured ESN owner can manage paid orders.",ephemeral=True)
        config.db.execute("INSERT INTO billing_notes(guild,user,note,actor) VALUES(?,?,?,?)",(interaction.guild.id,customer.id,note[:1000],interaction.user.id))
        config.db.commit()
        await interaction.response.send_message("Internal note saved. Payment status has NOT been verified.",ephemeral=True)

    @app_commands.command(name="hostingstatus",description="Show ESN Hosting operational status")
    @app_commands.guild_only()
    async def hostingstatus(self,interaction:discord.Interaction):
        await interaction.response.send_message(
            "ESN Hosting Manager is online. For actual server status use /serverstatus. "
            "This message does not certify node uptime.",ephemeral=True)

    @app_commands.command(name="templates",description="Show supported bot hosting templates")
    @app_commands.guild_only()
    async def templates(self,interaction:discord.Interaction):
        await interaction.response.send_message(
            "**Available bot runtimes:** Python and Node.js.\n"
            "Ask staff to provision a server through the panel. Automated provisioning is not yet enabled.",
            ephemeral=True)

async def setup(bot): await bot.add_cog(Commerce(bot))
