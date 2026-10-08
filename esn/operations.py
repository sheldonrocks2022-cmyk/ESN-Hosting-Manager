"""Safe Pterodactyl client actions and operational tooling."""
import os
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands,tasks
from . import config

BASE=os.getenv("PANEL_URL","https://panel.esnoffical.com").rstrip("/")
def api_key(): return os.getenv("PTERODACTYL_CLIENT_API_KEY","")
async def request(method,path,body=None):
    if not api_key(): raise RuntimeError("Set PTERODACTYL_CLIENT_API_KEY on the hosting server.")
    headers={"Authorization":f"Bearer {api_key()}","Accept":"Application/vnd.pterodactyl.v1+json","Content-Type":"application/json"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.request(method,BASE+path,headers=headers,json=body) as r:
            if r.status>=400: raise RuntimeError(f"Pterodactyl HTTP {r.status}")
            if r.status==204: return {}
            return await r.json()

class Operations(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.monitor.start()
    def cog_unload(self): self.monitor.cancel()

    @app_commands.command(name="serverpower",description="Start stop or restart your linked hosting server")
    @app_commands.guild_only()
    @app_commands.choices(action=[app_commands.Choice(name=a,value=a) for a in ("start","stop","restart")])
    async def serverpower(self,interaction:discord.Interaction,action:app_commands.Choice[str]):
        sid=config.get(interaction.guild.id,f"server:{interaction.user.id}")
        if not sid: return await interaction.response.send_message("Ask staff to link your hosting server first.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            await request("POST",f"/api/client/servers/{sid}/power",{"signal":action.value})
            await interaction.followup.send(f"Sent **{action.value}** to your linked server.",ephemeral=True)
        except (RuntimeError,aiohttp.ClientError,TimeoutError) as exc:
            await interaction.followup.send(f"Could not complete request: {exc}",ephemeral=True)

    @app_commands.command(name="backupcreate",description="Request a backup of your linked server")
    @app_commands.guild_only()
    async def backupcreate(self,interaction:discord.Interaction):
        sid=config.get(interaction.guild.id,f"server:{interaction.user.id}")
        if not sid: return await interaction.response.send_message("No linked server.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            await request("POST",f"/api/client/servers/{sid}/backups",{})
            await interaction.followup.send("Backup requested. Check the panel for completion.",ephemeral=True)
        except (RuntimeError,aiohttp.ClientError,TimeoutError) as exc:
            await interaction.followup.send(f"Backup request failed: {exc}",ephemeral=True)

    @app_commands.command(name="monitor",description="Enable or disable periodic node/API reachability alerts")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def monitor_command(self,interaction:discord.Interaction,enabled:bool):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server required.",ephemeral=True)
        config.put(interaction.guild.id,"monitor_enabled",int(enabled))
        await interaction.response.send_message(f"API monitor {'enabled' if enabled else 'disabled'}. Checks every 5 minutes.",ephemeral=True)

    @tasks.loop(minutes=5)
    async def monitor(self):
        if not api_key(): return
        for guild in self.bot.guilds:
            if config.get(guild.id,"monitor_enabled")!="1": continue
            try:
                await request("GET","/api/client")
                config.put(guild.id,"monitor_failures",0)
            except (RuntimeError,aiohttp.ClientError,TimeoutError):
                failures=int(config.get(guild.id,"monitor_failures","0"))+1
                config.put(guild.id,"monitor_failures",failures)
                if failures==3:
                    channel=guild.get_channel(int(config.get(guild.id,"status_channel","0")))
                    if isinstance(channel,discord.TextChannel):
                        try: await channel.send("⚠️ ESN Hosting API has failed three consecutive checks.",allowed_mentions=discord.AllowedMentions.none())
                        except discord.HTTPException: pass

    @monitor.before_loop
    async def before_monitor(self): await self.bot.wait_until_ready()

async def setup(bot): await bot.add_cog(Operations(bot))
