"""Persistent owner-only approval buttons and application decision DMs."""
import logging
import discord
from partner_permissions import OWNER_DISCORD_ID, review_partner

log = logging.getLogger(__name__)
GOLD = 0xD5AD65
GREEN = 0x35C98A
RED = 0xE35B69

def card(title, description, icon=None, color=GOLD):
    e = discord.Embed(title=title, description=description, color=color,
                      timestamp=discord.utils.utcnow())
    e.set_author(name="ESN HOSTING  •  PARTNER NETWORK", icon_url=icon)
    e.set_footer(text="Official ESN Hosting • Partner Applications", icon_url=icon)
    if icon:
        e.set_thumbnail(url=icon)
    return e

async def applicant_dm(bot, user_id, status, guild=None):
    icon = guild.icon.url if guild and guild.icon else None
    if status == "approved":
        e = card("APPLICATION APPROVED",
                 "Congratulations! Your ESN Hosting partner application has been **approved**.\n\n"
                 "Use **/partner link** in the ESN Discord server to get your personal Starter referral link. "
                 "Your initial commission rate is **5%** on eligible first-time purchases.",
                 icon, GREEN)
    else:
        e = card("APPLICATION NOT APPROVED",
                 "Your ESN Hosting partner application was **declined**. "
                 "If you have questions, please contact ESN Hosting support.",
                 icon, RED)
    try:
        user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        await user.send(embed=e)
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        log.warning("Could not DM partner applicant %s", user_id)
        return False

async def decide(bot, program, owner_id, applicant_id, status, guild=None):
    if str(owner_id) != OWNER_DISCORD_ID:
        raise PermissionError("Only the ESN owner can review applications.")
    current = program.db.execute(
        "SELECT status FROM partners WHERE discord_id=?", (str(applicant_id),)
    ).fetchone()
    if not current or current[0] != "pending":
        raise ValueError("This application is no longer pending.")
    review_partner(program, owner_id, applicant_id, status)
    return await applicant_dm(bot, applicant_id, status, guild)

class PartnerApprovalView(discord.ui.View):
    """Persistent view: survives restart; applicant ID encoded in custom IDs."""
    def __init__(self, bot, program):
        super().__init__(timeout=None)
        self.bot = bot
        self.program = program

    async def handle(self, interaction, status):
        if str(interaction.user.id) != OWNER_DISCORD_ID:
            return await interaction.response.send_message(
                embed=card("ACCESS DENIED", "Only the ESN Hosting owner can review partner applications.", color=RED),
                ephemeral=True)
        try:
            applicant_id = int(interaction.data["custom_id"].rsplit(":", 1)[1])
        except (KeyError, ValueError, TypeError):
            return await interaction.response.send_message("Invalid application ID.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            notified = await decide(self.bot, self.program, interaction.user.id, applicant_id,
                                    status, interaction.guild)
        except ValueError as exc:
            return await interaction.followup.send(
                embed=card("ALREADY REVIEWED", str(exc), color=RED), ephemeral=True)
        color = GREEN if status == "approved" else RED
        message = ("Approved" if status == "approved" else "Declined") + f" <@{applicant_id}>."
        if not notified:
            message += "\nApplicant DMs are closed; decision saved but DM not delivered."
        await interaction.followup.send(embed=card("APPLICATION REVIEWED", message, color=color), ephemeral=True)
        try:
            await interaction.message.edit(
                embed=card("APPLICATION REVIEWED", message, color=color), view=None)
        except discord.HTTPException:
            log.warning("Could not update reviewed application message")

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success,
                       custom_id="esn:partner:approve:0")
    async def approve_button(self, interaction, button):
        await self.handle(interaction, "approved")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger,
                       custom_id="esn:partner:deny:0")
    async def deny_button(self, interaction, button):
        await self.handle(interaction, "rejected")

    @classmethod
    def for_applicant(cls, bot, program, applicant_id):
        view = cls(bot, program)
        for button in view.children:
            if button.custom_id.endswith(":0"):
                button.custom_id = button.custom_id[:-1] + str(applicant_id)
        return view

async def notify_owner(bot, program, applicant, guild):
    icon = guild.icon.url if guild and guild.icon else None
    e = card("NEW PARTNER APPLICATION",
             f"**Applicant:** {applicant.mention}\n"
             f"**Discord ID:** \`{applicant.id}\`\n"
             f"**Server:** {guild.name if guild else 'Direct message'}\n\n"
             "Review this application using the buttons below. "
             "Only the ESN Hosting owner can approve or deny.",
             icon)
    try:
        owner = bot.get_user(int(OWNER_DISCORD_ID)) or await bot.fetch_user(int(OWNER_DISCORD_ID))
        await owner.send(embed=e, view=PartnerApprovalView.for_applicant(bot, program, applicant.id))
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        log.warning("Could not DM ESN owner about partner application %s", applicant.id)
        return False

def register_pending_views(bot, program):
    rows = program.db.execute("SELECT discord_id FROM partners WHERE status='pending'").fetchall()
    for (applicant_id,) in rows:
        bot.add_view(PartnerApprovalView.for_applicant(bot, program, applicant_id))
    log.info("Registered %d persistent partner approval views", len(rows))
