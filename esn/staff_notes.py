"""ESN Hosting staff-only ticket notes."""
import discord
from discord import app_commands
from discord.ext import commands
from . import config
from .luxury import luxury_send
from .tickets import ticket_owner

config.db.execute("CREATE TABLE IF NOT EXISTS staff_notes (id INTEGER PRIMARY KEY, guild INTEGER, channel INTEGER, actor INTEGER, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
config.db.commit()

class StaffNotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketnote", description="Save an internal note in this support ticket")
    @app_commands.guild_only()
    async def ticketnote(self, interaction: discord.Interaction, note: str):
        if not config.role_allowed(interaction.user) or ticket_owner(interaction.channel) is None:
            return await luxury_send(interaction, "Staff access inside an open ticket required.", ephemeral=True)
        if not 1 <= len(note) <= 1000:
            return await luxury_send(interaction, "Note must be 1 to 1000 characters.", ephemeral=True)
        config.db.execute("INSERT INTO staff_notes(guild,channel,actor,body) VALUES(?,?,?,?)",
                          (interaction.guild.id, interaction.channel.id, interaction.user.id, note))
        config.db.commit()
        config.audit(interaction.guild.id, "staff_note", interaction.user.id, str(interaction.channel.id))
        await luxury_send(interaction, "Internal staff note saved.", ephemeral=True)

    @app_commands.command(name="ticketnotes", description="View internal staff notes in this ticket")
    @app_commands.guild_only()
    async def ticketnotes(self, interaction: discord.Interaction):
        if not config.role_allowed(interaction.user) or ticket_owner(interaction.channel) is None:
            return await luxury_send(interaction, "Staff access inside an open ticket required.", ephemeral=True)
        rows = config.db.execute("SELECT actor,body FROM staff_notes WHERE guild=? AND channel=? ORDER BY id DESC LIMIT 5",
                                 (interaction.guild.id, interaction.channel.id)).fetchall()
        description = "\n\n".join(f"Staff {actor}: {discord.utils.escape_mentions(body)}" for actor, body in rows)
        await luxury_send(interaction, description[:3500] or "No internal notes.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StaffNotes(bot))
