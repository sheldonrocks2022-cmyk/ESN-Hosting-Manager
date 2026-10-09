"""Optional detailed partner application form and owner DM review."""
import discord
from discord import app_commands
from discord.ext import commands
from partner_approvals import notify_owner
from partner_permissions import OWNER_DISCORD_ID
from partner_program import PartnerProgram
import os
from .luxury import luxury_send

class ApplicationForm(discord.ui.Modal,title="ESN Hosting • Partner Application"):
    community=discord.ui.TextInput(label="Your community or platform",max_length=150,required=True)
    audience=discord.ui.TextInput(label="Estimated audience size",max_length=100,required=True)
    promotion=discord.ui.TextInput(label="How will you promote ESN Hosting?",style=discord.TextStyle.paragraph,max_length=750,required=True)
    experience=discord.ui.TextInput(label="Relevant experience (optional)",style=discord.TextStyle.paragraph,max_length=500,required=False)
    def __init__(self,bot):
        super().__init__(timeout=300)
        self.bot=bot
    async def on_submit(self,interaction):
        from . import config
        if interaction.guild and config.get(interaction.guild.id,"owner_lockdown","0")=="1":
            return await luxury_send(interaction,"Partner applications are temporarily paused.",ephemeral=True)
        program=PartnerProgram(os.getenv("PARTNER_DB_PATH","data/partners.sqlite3"))
        try:
            code=program.apply(str(interaction.user.id))
        except Exception:
            return await luxury_send(interaction,"You already have a partner application. Use /partner stats.",ephemeral=True)
        # Store answers in audit ledger, not in public Discord messages.
        with program.db:
            program.audit(str(interaction.user.id),"application_answers",
                          f"community={str(self.community.value)}; audience={str(self.audience.value)}; "
                          f"promotion={str(self.promotion.value)}; experience={str(self.experience.value)}")
        notified=await notify_owner(self.bot,program,interaction.user,interaction.guild)
        # Send the application details in a separate private DM to the owner.
        try:
            owner=self.bot.get_user(int(OWNER_DISCORD_ID)) or await self.bot.fetch_user(int(OWNER_DISCORD_ID))
            e=discord.Embed(title="ESN HOSTING  |  APPLICATION DETAILS",color=0xD5AD65)
            e.add_field(name="Applicant",value=interaction.user.mention,inline=False)
            for label,value in [("Community",self.community.value),("Audience",self.audience.value),
                                ("Promotion",self.promotion.value),("Experience",self.experience.value or "Not provided")]:
                e.add_field(name=label,value=str(value)[:1000],inline=False)
            if interaction.guild and interaction.guild.icon:e.set_thumbnail(url=interaction.guild.icon.url)
            await owner.send(embed=e)
        except (discord.Forbidden,discord.HTTPException,discord.NotFound):
            pass
        await luxury_send(interaction,
            f"Your application was submitted. **Status: Pending**\nReferral code: `{code}`\n"
            +("The owner was notified." if notified else "Owner DM unavailable; your application is safely recorded."),
            ephemeral=True)

class PartnerForms(commands.Cog):
    def __init__(self,bot):self.bot=bot
    @app_commands.command(name="partnerapplication",description="Complete the detailed ESN partner application")
    @app_commands.guild_only()
    async def partnerapplication(self,interaction:discord.Interaction):
        await interaction.response.send_modal(ApplicationForm(self.bot))

async def setup(bot):await bot.add_cog(PartnerForms(bot))
