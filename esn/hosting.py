"""Pterodactyl client API status with explicitly linked server ownership."""
import os
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from . import config

class Hosting(commands.Cog):
    def __init__(self,bot): self.bot=bot

    @app_commands.command(name="serverlink",description="Link a Pterodactyl server ID to a customer (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def serverlink(self,interaction:discord.Interaction,member:discord.Member,server_id:str):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        if not server_id.replace("-","").isalnum() or len(server_id)>64:
            return await interaction.response.send_message("Invalid server identifier.",ephemeral=True)
        config.put(interaction.guild.id,f"server:{member.id}",server_id)
        await interaction.response.send_message(f"Linked server \`{server_id}\` to {member.mention}.",ephemeral=True)

    @app_commands.command(name="serverstatus",description="Check your linked Pterodactyl server status")
    @app_commands.guild_only()
    async def serverstatus(self,interaction:discord.Interaction):
        sid=config.get(interaction.guild.id,f"server:{interaction.user.id}")
        if not sid: return await interaction.response.send_message("No server linked to your Discord account. Ask staff to use /serverlink.",ephemeral=True)
        key=os.getenv("PTERODACTYL_CLIENT_API_KEY","")
        base=os.getenv("PANEL_URL","https://panel.esnoffical.com").rstrip("/")
        if not key: return await interaction.response.send_message("Pterodactyl API key is not configured securely on the server.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                async with session.get(f"{base}/api/client/servers/{sid}/resources",headers={"Authorization":f"Bearer {key}","Accept":"Application/vnd.pterodactyl.v1+json"}) as response:
                    if response.status!=200:
                        return await interaction.followup.send(f"Panel returned HTTP {response.status}; check server link and API permissions.",ephemeral=True)
                    payload=await response.json()
            attrs=payload.get("attributes",{})
            resources=attrs.get("resources",{})
            await interaction.followup.send(
                f"**Server:** \`{sid}\`\n**State:** {attrs.get('current_state','unknown')}\n"
                f"**RAM:** {resources.get('memory_bytes',0)//1048576} MiB\n"
                f"**Disk:** {resources.get('disk_bytes',0)//1048576} MiB",
                ephemeral=True)
        except (aiohttp.ClientError,TimeoutError,ValueError):
            await interaction.followup.send("Unable to reach the panel. Try again later.",ephemeral=True)

async def setup(bot): await bot.add_cog(Hosting(bot))
