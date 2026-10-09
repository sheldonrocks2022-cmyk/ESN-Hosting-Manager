from .luxury import luxury_send, luxury_followup
"""Discord-side configuration commands; only Manage Server can configure."""
import discord
from discord import app_commands
from discord.ext import commands
from . import config

class Admin(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="configure",description="Set an ESN Hosting Manager role or channel")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(setting=[
        app_commands.Choice(name="Staff role",value="staff_role"),
        app_commands.Choice(name="Ticket category",value="ticket_category"),
        app_commands.Choice(name="Log channel",value="log_channel"),
        app_commands.Choice(name="Security alert channel",value="security_channel"),
        app_commands.Choice(name="Status channel",value="status_channel")])
    async def configure(self, interaction:discord.Interaction, setting:app_commands.Choice[str], role:discord.Role|None=None, channel:discord.abc.GuildChannel|None=None):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction, "Manage Server required.",ephemeral=True)
        if setting.value=="staff_role":
            if not role: return await luxury_send(interaction, "Select a role.",ephemeral=True)
            value=role.id
        else:
            if not channel: return await luxury_send(interaction, "Select a channel or category.",ephemeral=True)
            if setting.value=="ticket_category" and not isinstance(channel,discord.CategoryChannel):
                return await luxury_send(interaction, "Choose a category.",ephemeral=True)
            value=channel.id
        config.put(interaction.guild.id,setting.value,value)
        await luxury_send(interaction, f"Saved **{setting.name}**. This survives restarts.",ephemeral=True)

    @app_commands.command(name="dashboard",description="View ESN Hosting Manager configuration")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def dashboard(self, interaction:discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction, "Manage Server required.",ephemeral=True)
        names=["staff_role","ticket_category","log_channel","security_channel","status_channel"]
        rows=[f"**{name}:** {config.get(interaction.guild.id,name,'Not set')}" for name in names]
        await luxury_send(interaction, "**ESN Hosting Manager**\n"+"\n".join(rows)+"\nUse /configure to change settings.",ephemeral=True)


    @app_commands.command(name="ownerstatus",description="Check whether your Discord account is configured as ESN owner")
    @app_commands.guild_only()
    async def ownerstatus(self, interaction:discord.Interaction):
        await luxury_send(interaction, 
            "You are the configured ESN owner." if config.owner_allowed(interaction.user)
            else "Your Discord ID is not the configured owner. Set OWNER_DISCORD_ID in the server .env to your numeric Discord User ID, then restart.",
            ephemeral=True)

async def setup(bot): await bot.add_cog(Admin(bot))
