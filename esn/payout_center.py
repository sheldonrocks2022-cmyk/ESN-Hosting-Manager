"""Partner payout requests: manual owner review, no transfers."""
import os
import discord
from discord import app_commands
from discord.ext import commands
from . import config
from .luxury import luxury_send, luxury_embed
from partner_program import PartnerProgram
from partner_permissions import require_owner, OWNER_DISCORD_ID

config.db.execute("CREATE TABLE IF NOT EXISTS payout_requests (id INTEGER PRIMARY KEY, partner TEXT NOT NULL, guild INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
config.db.commit()

class PayoutCenter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="payoutrequest", description="Request an owner review of eligible partner commissions")
    @app_commands.guild_only()
    async def payoutrequest(self, interaction: discord.Interaction):
        program = PartnerProgram(os.getenv("PARTNER_DB_PATH", "data/partners.sqlite3"))
        partner = program.db.execute("SELECT id FROM partners WHERE discord_id=? AND status='approved'", (str(interaction.user.id),)).fetchone()
        if not partner:
            return await luxury_send(interaction, "Approved partner status required.", ephemeral=True)
        cents = program.db.execute("SELECT COALESCE(SUM(commission_cents),0) FROM referrals WHERE partner_id=? AND state='eligible'", (partner[0],)).fetchone()[0]
        if cents <= 0:
            return await luxury_send(interaction, "No eligible commissions are currently recorded.", ephemeral=True)
        existing = config.db.execute("SELECT id FROM payout_requests WHERE partner=? AND status='pending'", (str(interaction.user.id),)).fetchone()
        if existing:
            return await luxury_send(interaction, "A payout review request is already pending.", ephemeral=True)
        config.db.execute("INSERT INTO payout_requests(partner,guild) VALUES(?,?)", (str(interaction.user.id), interaction.guild.id))
        config.db.commit()
        try:
            owner = self.bot.get_user(int(OWNER_DISCORD_ID)) or await self.bot.fetch_user(int(OWNER_DISCORD_ID))
            await owner.send(embed=luxury_embed(interaction, f"Partner: {interaction.user.mention}\nEligible ledger amount: USD {cents/100:.2f}\nReview using /payoutreviews. No funds are transferred automatically.", title="ESN HOSTING | PAYOUT REQUEST"))
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass
        await luxury_send(interaction, "Payout review request saved. The owner must review it manually.", ephemeral=True)

    @app_commands.command(name="payoutreviews", description="Owner: list pending payout requests")
    @app_commands.guild_only()
    async def payoutreviews(self, interaction: discord.Interaction):
        try:
            require_owner(interaction.user.id)
        except PermissionError:
            return await luxury_send(interaction, "Owner only.", ephemeral=True)
        rows = config.db.execute("SELECT id,partner FROM payout_requests WHERE status='pending' ORDER BY id DESC LIMIT 15").fetchall()
        await luxury_send(interaction, "\n".join(f"Request {rid}: <@{partner}>" for rid, partner in rows) or "No pending requests.", ephemeral=True)

    @app_commands.command(name="payoutreview", description="Owner: review a partner payout request")
    @app_commands.guild_only()
    @app_commands.choices(decision=[app_commands.Choice(name="Approve for manual handling", value="approved"), app_commands.Choice(name="Decline", value="declined")])
    async def payoutreview(self, interaction: discord.Interaction, request_id: int, decision: app_commands.Choice[str]):
        try:
            require_owner(interaction.user.id)
        except PermissionError:
            return await luxury_send(interaction, "Owner only.", ephemeral=True)
        row = config.db.execute("SELECT partner FROM payout_requests WHERE id=? AND status='pending'", (request_id,)).fetchone()
        if not row:
            return await luxury_send(interaction, "Pending request not found.", ephemeral=True)
        config.db.execute("UPDATE payout_requests SET status=? WHERE id=?", (decision.value, request_id))
        config.db.commit()
        config.audit(interaction.guild.id, "payout_review", interaction.user.id, f"{request_id}: {decision.value}")
        try:
            user = self.bot.get_user(int(row[0])) or await self.bot.fetch_user(int(row[0]))
            await user.send(embed=luxury_embed(interaction, f"Your payout request {request_id} was {decision.value}. This does not mean funds were transferred.", title="ESN HOSTING | PAYOUT REVIEW"))
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass
        await luxury_send(interaction, f"Request {request_id}: {decision.value}. No payment transferred.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PayoutCenter(bot))
