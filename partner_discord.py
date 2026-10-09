"""discord.py 2.x slash commands for the ESN partner program.

Register with bot.tree.add_command(PartnerGroup(program)).
Requires discord.py>=2.3. Never expose settlement to non-owner accounts.
"""
import discord
from discord import app_commands
from partner_permissions import require_owner, review_partner, settle_commission
from partner_approvals import notify_owner, decide

BRAND = 0x5865F2

def premium(interaction: discord.Interaction, title: str, description: str, *, color=BRAND):
    """Use the invoking guild's icon for every bot response embed."""
    guild = interaction.guild
    icon = guild.icon.url if guild and guild.icon else None
    name = guild.name if guild else "ESN Hosting"
    e = discord.Embed(title=title, description=description, color=color,
                      timestamp=discord.utils.utcnow())
    e.set_author(name=name + " • Partner Program", icon_url=icon)
    e.set_footer(text="ESN Hosting • Official Partner Network", icon_url=icon)
    if icon:
        e.set_thumbnail(url=icon)
    return e

class PartnerGroup(app_commands.Group):
    def __init__(self, program):
        super().__init__(name="partner", description="ESN Hosting partner program")
        self.program = program

    async def send(self, interaction, title, message, *, error=False):
        e = premium(interaction, title, message, color=0xED4245 if error else BRAND)
        if interaction.response.is_done():
            await interaction.followup.send(embed=e, ephemeral=True)
        else:
            await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="apply", description="Apply to join the ESN partner network")
    async def apply(self, interaction: discord.Interaction):
        from esn import config
        if interaction.guild and config.get(interaction.guild.id,'owner_lockdown','0') == '1':
            return await self.send(interaction,'Applications paused','The ESN owner has temporarily paused new partner applications.',error=True)
        try:
            code = self.program.apply(str(interaction.user.id))
            notified = await notify_owner(interaction.client, self.program, interaction.user, interaction.guild)
            await self.send(interaction,"Application received",
                            "Your application is **pending owner approval**.\n"
                            f"Your private referral code: `{code}`\n" + ("Owner notified by DM." if notified else "Owner DM unavailable; application saved."))
        except Exception:
            await self.send(interaction,"Application already exists",
                            "You may already have an application. Use /partner stats.",error=True)

    @app_commands.command(name="stats", description="View your partner dashboard")
    async def stats(self, interaction: discord.Interaction):
        s = self.program.stats(str(interaction.user.id))
        if not s:
            return await self.send(interaction,"Not enrolled","Use /partner apply to get started.",error=True)
        await self.send(interaction,"Your partner dashboard",
                        f"**Status:** {s['status'].title()}\n"
                        f"**Referral code:** `{s['code']}`\n"
                        f"**Verified referrals:** {s['verified']}\n"
                        f"**Current commission rate:** {s['rate']}%\n"
                        f"**Recorded commissions:** ${s['earnings_cents']/100:.2f}\n\n"
                        "Recorded commissions are not necessarily available for payout.")

    @app_commands.command(name="approve", description="Owner: approve a partner")
    async def approve(self, interaction: discord.Interaction, member: discord.User):
        try:
            require_owner(interaction.user.id)
            notified = await decide(interaction.client, self.program, interaction.user.id, member.id, "approved", interaction.guild)
            await self.send(interaction,"Partner approved",f"{member.mention} is now approved." + ("" if notified else " Applicant DM could not be delivered."))
        except PermissionError:
            await self.send(interaction,"Access denied","Only the ESN owner can approve partners.",error=True)
        except ValueError as exc:
            await self.send(interaction,"Unable to approve",str(exc),error=True)

    @app_commands.command(name="reject", description="Owner: reject a partner")
    async def reject(self, interaction: discord.Interaction, member: discord.User):
        try:
            require_owner(interaction.user.id)
            notified = await decide(interaction.client, self.program, interaction.user.id, member.id, "rejected", interaction.guild)
            await self.send(interaction,"Partner rejected",f"{member.mention}'s application was rejected." + ("" if notified else " Applicant DM could not be delivered."))
        except PermissionError:
            await self.send(interaction,"Access denied","Owner only.",error=True)
        except ValueError as exc:
            await self.send(interaction,"Unable to reject",str(exc),error=True)

    @app_commands.command(name="payout", description="Owner: record a verified manual payout")
    @app_commands.describe(payment_id="Stripe payment ID", state="Eligible, paid or reversed")
    @app_commands.choices(state=[
        app_commands.Choice(name="Eligible",value="eligible"),
        app_commands.Choice(name="Paid",value="paid"),
        app_commands.Choice(name="Reversed",value="reversed")])
    async def payout(self, interaction: discord.Interaction, payment_id: str,
                     state: app_commands.Choice[str]):
        try:
            require_owner(interaction.user.id)
            settle_commission(self.program, interaction.user.id, payment_id, state.value)
            await self.send(interaction,"Commission updated",
                            f"Payment `{payment_id}` marked **{state.value}**.\n"
                            "This action does not transfer money.")
        except PermissionError:
            await self.send(interaction,"Access denied","Owner only.",error=True)
        except ValueError as exc:
            await self.send(interaction,"Update refused",str(exc),error=True)

    @app_commands.command(name="pending", description="Owner: list pending partner applications")
    async def pending(self, interaction: discord.Interaction):
        try:
            require_owner(interaction.user.id)
        except PermissionError:
            return await self.send(interaction, "Access denied", "Owner only.", error=True)
        rows = self.program.db.execute(
            "SELECT discord_id,created_at FROM partners WHERE status='pending' ORDER BY id LIMIT 15"
        ).fetchall()
        if not rows:
            return await self.send(interaction, "Partner applications", "No pending applications.")
        description = "\n".join(
            f"• <@{discord_id}> — {created_at[:10]}" for discord_id, created_at in rows
        )
        await self.send(interaction, "Pending applications", description)

    @app_commands.command(name="link", description="Get your official ESN Starter referral link")
    async def link(self, interaction: discord.Interaction):
        s = self.program.stats(str(interaction.user.id))
        if not s or s["status"] != "approved":
            return await self.send(interaction, "Not approved", "Apply with /partner apply and wait for owner approval.", error=True)
        from urllib.parse import urlencode
        url = "https://buy.stripe.com/9B628scRZ2jZ9Nl5pZdnW04?" + urlencode({"client_reference_id": s["code"]})
        await self.send(interaction, "Your ESN Starter referral link",
                        f"Share this link for the monthly Starter plan:\n{url}\n\n"
                        "Commissions are recorded only for eligible first-time paid subscriptions.")
