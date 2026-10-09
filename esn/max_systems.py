"""ESN MAX: Discord configuration, customer portal, diagnostics and owner lockdown."""
import os
import re
import discord
from discord import app_commands
from discord.ext import commands
from . import config
from .luxury import luxury_send, luxury_embed
from partner_permissions import require_owner

SETTINGS = {
 "ticket_category":"Ticket category", "staff_role":"Staff role",
 "log_channel":"Log channel", "security_channel":"Security alerts",
 "status_channel":"Hosting status", "partner_channel":"Partner notifications",
}
def locked(guild):
    return config.get(guild.id,"owner_lockdown","0")=="1"

class ConfigSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="View a configuration area",options=[
            discord.SelectOption(label="Support and Tickets",value="tickets",emoji="🎟️"),
            discord.SelectOption(label="Hosting and Monitoring",value="hosting",emoji="🖥️"),
            discord.SelectOption(label="Security",value="security",emoji="🛡️"),
            discord.SelectOption(label="Partner Program",value="partners",emoji="🤝"),
        ])
    async def callback(self, interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction,"Manage Server permission required.",ephemeral=True)
        groups={"tickets":["ticket_category","staff_role","log_channel"],
                "hosting":["status_channel","monitor_enabled"],
                "security":["security_channel","security_enabled","honeypot_enabled","owner_lockdown"],
                "partners":["partner_channel"]}
        rows=[f"**{key}:** `{config.get(interaction.guild.id,key,'Not set')}`" for key in groups[self.values[0]]]
        await luxury_send(interaction,"\n".join(rows)+"\n\nUse **/esnset** to change channels and roles.",ephemeral=True)

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ConfigSelect())

class MaxSystems(commands.Cog):
    def __init__(self,bot): self.bot=bot

    @app_commands.command(name="esnconfig",description="Interactive ESN Hosting configuration dashboard")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def esnconfig(self,interaction:discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction,"Manage Server permission required.",ephemeral=True)
        await interaction.response.send_message(embed=luxury_embed(interaction,
            "Configure tickets, monitoring, security, and partner alerts through Discord.\n"
            "Choose a category below or use **/esnset** to update a setting.",
            title="ESN HOSTING  |  CONFIGURATION CENTER"),view=ConfigView(),ephemeral=True)

    @app_commands.command(name="esnset",description="Set an ESN channel or role without editing files")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(setting=[app_commands.Choice(name=name,value=key) for key,name in SETTINGS.items()])
    async def esnset(self,interaction:discord.Interaction,setting:app_commands.Choice[str],
                     channel:discord.abc.GuildChannel|None=None,role:discord.Role|None=None):
        if not interaction.user.guild_permissions.manage_guild:
            return await luxury_send(interaction,"Manage Server permission required.",ephemeral=True)
        key=setting.value
        if key=="staff_role":
            if not role:return await luxury_send(interaction,"Select a staff role.",ephemeral=True)
            obj=role
        else:
            if not channel:return await luxury_send(interaction,"Select a channel.",ephemeral=True)
            if key=="ticket_category" and not isinstance(channel,discord.CategoryChannel):
                return await luxury_send(interaction,"Ticket category must be a Discord category.",ephemeral=True)
            if key!="ticket_category" and not isinstance(channel,discord.TextChannel):
                return await luxury_send(interaction,"Select a text channel.",ephemeral=True)
            obj=channel
        config.put(interaction.guild.id,key,obj.id)
        config.audit(interaction.guild.id,"setting_changed",interaction.user.id,f"{key}={obj.id}")
        await luxury_send(interaction,f"**{setting.name}** saved as {obj.mention}.",ephemeral=True)

    @app_commands.command(name="myhosting",description="Your private ESN Hosting customer portal")
    @app_commands.guild_only()
    async def myhosting(self,interaction:discord.Interaction):
        sid=config.get(interaction.guild.id,f"server:{interaction.user.id}")
        trial=config.db.execute("SELECT status,expires_at FROM trials WHERE user=?",(interaction.user.id,)).fetchone()
        sub=config.db.execute("SELECT plan,status,expires_at FROM subscriptions WHERE guild=? AND user=? ORDER BY rowid DESC LIMIT 1",
                              (interaction.guild.id,interaction.user.id)).fetchone()
        tickets=[c.mention for c in interaction.guild.text_channels if (c.topic or "")==f"esnhm-owner:{interaction.user.id}"]
        desc=(f"**Linked server:** `{sid or 'Not linked'}`\n"
              f"**Subscription record:** {sub[0]+' — '+sub[1] if sub else 'Not linked or verified'}\n"
              f"**Trial:** {trial[0] if trial else 'None'}\n"
              f"**Open tickets:** {', '.join(tickets[:3]) or 'None'}\n\n"
              "Use **/serverstatus**, **/serverpower**, **/backupcreate** or open a support ticket. "
              "Subscription records here are local records, not live Stripe verification.")
        await interaction.response.send_message(embed=luxury_embed(interaction,desc,title="ESN HOSTING  |  MY CUSTOMER PORTAL"),ephemeral=True)

    @app_commands.command(name="diagnose",description="Diagnose common Python and Node.js hosting errors")
    @app_commands.guild_only()
    @app_commands.describe(error="Paste a short error message, without tokens or private keys")
    async def diagnose(self,interaction:discord.Interaction,error:str):
        message=error.lower()[:1500]
        rules=[
          (("modulenotfounderror","no module named"),"Python dependency missing. Add the package to requirements.txt and restart."),
          (("cannot find module","err_module_not_found"),"Node.js module missing. Check package.json and install dependencies."),
          (("invalid token","token was provided"),"Bot token is invalid or missing. Update it privately in your panel. Never share it."),
          (("enoent","no such file or directory"),"File or directory missing. Check the startup path and uploaded files."),
          (("permission denied","eacces"),"Process lacks permission to access the requested file or port."),
          (("429","rate limit"),"Too many requests. Add backoff and avoid repeated rapid API calls."),
          (("syntaxerror","unexpected token"),"Code syntax issue. Inspect the referenced file and line number."),
          (("address already in use","eaddrinuse"),"A port is already occupied by another process."),
        ]
        answer=next((tip for keys,tip in rules if any(k in message for k in keys)),
                    "No known pattern matched. Check the first traceback line, runtime version and startup file. Open a support ticket for help.")
        await luxury_send(interaction,answer+"\n\n**Security:** Never post API keys, bot tokens, or customer payment details.",ephemeral=True)

    @app_commands.command(name="esnlockdown",description="Owner: pause sensitive management actions")
    @app_commands.guild_only()
    async def esnlockdown(self,interaction:discord.Interaction,enabled:bool):
        try:require_owner(interaction.user.id)
        except PermissionError:return await luxury_send(interaction,"Owner access required.",ephemeral=True)
        config.put(interaction.guild.id,"owner_lockdown",int(enabled))
        config.audit(interaction.guild.id,"lockdown",interaction.user.id,"enabled" if enabled else "disabled")
        await luxury_send(interaction,
            ("**Lockdown ON.** New partner applications and sensitive server actions are paused."
             if enabled else "**Lockdown OFF.** Normal operations restored.")
            +" Existing customer servers are not shut down.",ephemeral=True)

async def setup(bot):await bot.add_cog(MaxSystems(bot))
