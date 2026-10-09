"""ESN Hosting premium command center: dashboards, partners, billing and support."""
import os
import discord
from discord import app_commands
from discord.ext import commands
from . import config
from .luxury import luxury_embed, luxury_send, luxury_followup
from partner_program import PartnerProgram
from partner_permissions import require_owner

def ledger():
    return PartnerProgram(os.getenv("PARTNER_DB_PATH", "data/partners.sqlite3"))

class MainMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
    @discord.ui.button(label="Hosting Plans", style=discord.ButtonStyle.primary, emoji="🖥️")
    async def plans(self, interaction, button):
        await luxury_send(interaction, "ESN Starter is a monthly subscription. Contact the official ESN Hosting team for current availability and support.\n**Starter checkout:** https://buy.stripe.com/9B628scRZ2jZ9Nl5pZdnW04", ephemeral=True)
    @discord.ui.button(label="Open Support", style=discord.ButtonStyle.secondary, emoji="🎟️")
    async def support(self, interaction, button):
        await luxury_send(interaction, "Use **/ticketpanel** to publish the support panel (staff) or choose an existing ticket panel in this server.", ephemeral=True)
    @discord.ui.button(label="Partner Program", style=discord.ButtonStyle.secondary, emoji="🤝")
    async def partners(self, interaction, button):
        await luxury_send(interaction, "Apply with **/partner apply**. Approved partners can get a referral link with **/partner link**, and check earnings using **/partner stats**.", ephemeral=True)
    @discord.ui.button(label="My Server", style=discord.ButtonStyle.secondary, emoji="📊")
    async def server(self, interaction, button):
        await luxury_send(interaction, "Use **/serverstatus** to view a linked server, or **/serverpower** to manage your own server.", ephemeral=True)

class PremiumCenter(commands.Cog):
    def __init__(self, bot):
        self.bot=bot

    @app_commands.command(name="esnmenu",description="Open the luxury ESN Hosting control center")
    @app_commands.guild_only()
    async def esnmenu(self, interaction:discord.Interaction):
        await interaction.response.send_message(
            embed=luxury_embed(interaction, "**WELCOME TO ESN HOSTING**\nManage your hosting, open support, and explore the partner network using the buttons below.", title="ESN HOSTING  |  EXECUTIVE CONSOLE"),
            view=MainMenu(), ephemeral=True)

    @app_commands.command(name="partnerleaderboard",description="See the top ESN partners by verified referrals")
    @app_commands.guild_only()
    async def partnerleaderboard(self, interaction:discord.Interaction):
        db=ledger().db
        rows=db.execute("""SELECT p.discord_id, COUNT(r.id) AS total
            FROM partners p LEFT JOIN referrals r ON r.partner_id=p.id AND r.state IN ('held','eligible','paid')
            WHERE p.status='approved' GROUP BY p.id ORDER BY total DESC,p.id LIMIT 10""").fetchall()
        lines=[f"**{i}.** <@{uid}> — **{count}** verified" for i,(uid,count) in enumerate(rows,1)]
        await luxury_send(interaction, "\n".join(lines) if lines else "No approved partners yet.", ephemeral=True)

    @app_commands.command(name="ownercenter",description="Owner-only executive hosting and partner overview")
    @app_commands.guild_only()
    async def ownercenter(self, interaction:discord.Interaction):
        try: require_owner(interaction.user.id)
        except PermissionError:
            return await luxury_send(interaction,"Owner access required.",ephemeral=True)
        db=ledger().db
        pending=db.execute("SELECT COUNT(*) FROM partners WHERE status='pending'").fetchone()[0]
        approved=db.execute("SELECT COUNT(*) FROM partners WHERE status='approved'").fetchone()[0]
        held=db.execute("SELECT COALESCE(SUM(commission_cents),0) FROM referrals WHERE state='held'").fetchone()[0]
        paid=db.execute("SELECT COALESCE(SUM(commission_cents),0) FROM referrals WHERE state='paid'").fetchone()[0]
        tickets=sum(1 for c in interaction.guild.text_channels if (c.topic or "").startswith("esnhm-owner:"))
        text=(f"**Pending applications:** {pending}\n**Approved partners:** {approved}\n"
              f"**Held commissions:** ${held/100:.2f}\n**Recorded paid commissions:** ${paid/100:.2f}\n"
              f"**Open support tickets:** {tickets}\n\n"
              "Use **/partner pending** to review applications. Financial totals here are partner-ledger records, not Stripe revenue.")
        await interaction.response.send_message(embed=luxury_embed(interaction,text,title="ESN HOSTING  |  OWNER EXECUTIVE DASHBOARD"),ephemeral=True)

    @app_commands.command(name="supportguide",description="Get help with common Discord bot hosting issues")
    @app_commands.guild_only()
    @app_commands.choices(topic=[
        app_commands.Choice(name="Bot offline",value="offline"),
        app_commands.Choice(name="Python startup",value="python"),
        app_commands.Choice(name="Node.js startup",value="node"),
        app_commands.Choice(name="Billing",value="billing")])
    async def supportguide(self, interaction:discord.Interaction, topic:app_commands.Choice[str]):
        guides={
            "offline":"Check your panel console for the first error, verify your startup file and token are configured privately, then restart once. Do not paste tokens in tickets.",
            "python":"Check that MAIN_FILE points to the correct script and all dependencies are in requirements.txt. Read the first Python traceback in the console.",
            "node":"Check package.json, the entry file, Node.js version, and the console error. Install dependencies before starting.",
            "billing":"Only pay through official ESN Hosting payment methods. For billing questions open a private ticket; never share card details or Stripe secret keys."
        }
        await luxury_send(interaction,guides[topic.value],ephemeral=True)

    @app_commands.command(name="ticketfeedback",description="Rate your ESN support experience")
    @app_commands.guild_only()
    @app_commands.choices(rating=[app_commands.Choice(name=f"{n} stars",value=n) for n in range(1,6)])
    async def ticketfeedback(self,interaction:discord.Interaction,rating:app_commands.Choice[int]):
        channel=interaction.channel
        if not isinstance(channel,discord.TextChannel) or not (channel.topic or "").startswith("esnhm-"):
            return await luxury_send(interaction,"Use this inside your support ticket.",ephemeral=True)
        topic=channel.topic or ""
        if not (topic.startswith(f"esnhm-owner:{interaction.user.id}") or topic.startswith(f"esnhm-archived:{interaction.user.id}")):
            return await luxury_send(interaction,"Only the ticket customer can submit feedback.",ephemeral=True)
        key=f"feedback:{channel.id}"
        if config.get(interaction.guild.id,key):
            return await luxury_send(interaction,"Feedback has already been submitted for this ticket.",ephemeral=True)
        config.put(interaction.guild.id,key,f"{interaction.user.id}:{rating.value}")
        config.audit(interaction.guild.id,"ticket_feedback",interaction.user.id,f"ticket={channel.id};stars={rating.value}")
        await luxury_send(interaction,f"Thank you! Your **{rating.value}/5** support rating was recorded.",ephemeral=True)

    @app_commands.command(name="securityaudit",description="Owner: view the latest security and support audit events")
    @app_commands.guild_only()
    async def securityaudit(self,interaction:discord.Interaction):
        try: require_owner(interaction.user.id)
        except PermissionError:
            return await luxury_send(interaction,"Owner access required.",ephemeral=True)
        rows=config.db.execute("SELECT kind,actor,created_at FROM incidents WHERE guild=? ORDER BY id DESC LIMIT 10",(interaction.guild.id,)).fetchall()
        msg="\n".join(f"**{kind}** · `{actor}` · {stamp}" for kind,actor,stamp in rows) or "No audit events recorded."
        await luxury_send(interaction,msg,ephemeral=True)

async def setup(bot):
    await bot.add_cog(PremiumCenter(bot))
