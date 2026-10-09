"""Read-only owner Stripe subscription visibility. No refunds or payment creation."""
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from .luxury import luxury_send, luxury_followup
from partner_permissions import require_owner

class BillingCenter(commands.Cog):
    def __init__(self, bot): self.bot=bot

    def client(self):
        import stripe
        key=os.getenv("STRIPE_SECRET_KEY")
        if not key: raise RuntimeError("Stripe key is not configured.")
        stripe.api_key=key
        return stripe

    @app_commands.command(name="stripepayments",description="Owner: review latest Stripe payments")
    @app_commands.guild_only()
    async def stripepayments(self,interaction:discord.Interaction):
        try: require_owner(interaction.user.id)
        except PermissionError: return await luxury_send(interaction,"Owner access required.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            def fetch():
                stripe=self.client()
                return stripe.PaymentIntent.list(limit=8).data
            payments=await asyncio.to_thread(fetch)
            lines=[f"**{p.get('status','unknown')}** · ${p.get('amount_received',0)/100:.2f} {p.get('currency','usd').upper()} · `{p.id}`" for p in payments]
            await luxury_followup(interaction,"\n".join(lines) if lines else "No payments found.",ephemeral=True)
        except Exception:
            await luxury_followup(interaction,"Stripe lookup failed. Check restricted-key permissions and server logs.",ephemeral=True)

    @app_commands.command(name="stripesubscription",description="Owner: verify a Stripe subscription ID")
    @app_commands.guild_only()
    async def stripesubscription(self,interaction:discord.Interaction,subscription_id:str):
        try: require_owner(interaction.user.id)
        except PermissionError: return await luxury_send(interaction,"Owner access required.",ephemeral=True)
        if not subscription_id.startswith("sub_") or len(subscription_id)>128:
            return await luxury_send(interaction,"Enter a valid Stripe subscription ID.",ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            sub=await asyncio.to_thread(lambda:self.client().Subscription.retrieve(subscription_id))
            await luxury_followup(interaction,
                f"**Subscription:** `{sub.id}`\n**Status:** {sub.status}\n"
                f"**Cancel at period end:** {bool(sub.get('cancel_at_period_end'))}\n"
                "This is read-only; no billing changes were made.",ephemeral=True)
        except Exception:
            await luxury_followup(interaction,"Could not retrieve subscription. Check ID and Stripe API permissions.",ephemeral=True)

async def setup(bot): await bot.add_cog(BillingCenter(bot))
