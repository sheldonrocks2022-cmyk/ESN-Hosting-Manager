"""Standalone ESN Hosting partner Discord bot.
Requires discord.py>=2.3 and DISCORD_BOT_TOKEN in environment.
Run: python partner_bot.py
"""
import os
import logging
import discord
from discord.ext import commands
from partner_program import PartnerProgram
from partner_discord import PartnerGroup, premium

logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
program = PartnerProgram(os.environ.get("PARTNER_DB_PATH", "partners.sqlite3"))

@bot.event
async def on_ready():
    logging.info("Partner bot ready: %s", bot.user)

@bot.event
async def setup_hook():
    bot.tree.add_command(PartnerGroup(program))
    guild_id = os.environ.get("TEST_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

@bot.tree.error
async def command_error(interaction: discord.Interaction, error):
    logging.exception("Slash command failed", exc_info=error)
    embed = premium(interaction, "Something went wrong",
                    "We couldn't complete that request. Please try again or contact ESN support.",
                    color=0xED4245)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        logging.exception("Failed to send command error embed")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_BOT_TOKEN in the environment")
    bot.run(token)
