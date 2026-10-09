"""ESN Hosting Manager MAX — initial functional foundation."""
import os
import logging
import sqlite3
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from esn.luxury import luxury_send, luxury_followup, luxury_embed
from partner_program import PartnerProgram
from partner_discord import PartnerGroup
from stripe_polling import polling_loop

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID") or "0")
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID") or "0")
Path("data").mkdir(exist_ok=True)
DB = sqlite3.connect("data/settings.sqlite3")
DB.execute("CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER, setting TEXT, value INTEGER, PRIMARY KEY (guild_id, setting))")
DB.commit()

def setting(guild_id: int, name: str, fallback: int = 0) -> int:
    row = DB.execute("SELECT value FROM settings WHERE guild_id=? AND setting=?", (guild_id, name)).fetchone()
    return int(row[0]) if row else fallback

def save_setting(guild_id: int, name: str, value: int) -> None:
    DB.execute("INSERT INTO settings(guild_id,setting,value) VALUES(?,?,?) ON CONFLICT(guild_id,setting) DO UPDATE SET value=excluded.value", (guild_id, name, value))
    DB.commit()
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
partner_program = PartnerProgram(os.getenv("PARTNER_DB_PATH", "data/partners.sqlite3"))

def is_staff(member: discord.Member) -> bool:
    role_id = setting(member.guild.id, 'staff_role', STAFF_ROLE_ID)
    return member.guild_permissions.manage_guild or (role_id != 0 and any(role.id == role_id for role in member.roles))

class TicketSelect(discord.ui.Select):
    def __init__(self):
        choices = [
            discord.SelectOption(label="General Support", value="general", emoji="💬"),
            discord.SelectOption(label="Hosting Support", value="hosting", emoji="🖥️"),
            discord.SelectOption(label="Billing & Orders", value="billing", emoji="💳"),
            discord.SelectOption(label="14-Day Free Trial", value="trial", emoji="🎁"),
            discord.SelectOption(label="Partnerships", value="partners", emoji="🤝"),
        ]
        super().__init__(placeholder="Choose a support category...", options=choices, custom_id="esnhm:ticket:select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            return await luxury_send(interaction, "Use this panel in a server.", ephemeral=True)
        category_id = setting(guild.id, "ticket_category", TICKET_CATEGORY_ID)
        if not category_id:
            return await luxury_send(interaction, "Ticket category is not configured.", ephemeral=True)
        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            return await luxury_send(interaction, "Configured ticket category was not found.", ephemeral=True)
        staff_id = setting(guild.id, "staff_role", STAFF_ROLE_ID)
        staff_role = guild.get_role(staff_id) if staff_id else None
        if staff_role is None:
            return await luxury_send(interaction, "Staff role is not configured.", ephemeral=True)
        # One open ticket per user, preventing duplicate channels and spam.
        for channel in category.text_channels:
            if channel.topic == f"esnhm-owner:{interaction.user.id}":
                return await luxury_send(interaction, f"You already have a ticket: {channel.mention}", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        perms = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        try:
            channel = await guild.create_text_channel(
                name=f"hm-{self.values[0]}-{interaction.user.id}",
                category=category,
                topic=f"esnhm-owner:{interaction.user.id}",
                overwrites=perms,
                reason="ESN Hosting Manager support ticket",
            )
            await channel.send(
                f"{interaction.user.mention} {staff_role.mention}\n"
                f"**ESN Hosting — {self.values[0].title()} Ticket**\n"
                "Explain what you need help with. Staff can close this using `/ticketclose`.",
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )
            await luxury_followup(interaction, f"Ticket created: {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await luxury_followup(interaction, "I need Manage Channels and permission to view the ticket category.", ephemeral=True)

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    logging.info("Connected as %s", bot.user)

@bot.event
async def setup_hook():
    for extension in ('esn.admin', 'esn.security', 'esn.trials', 'esn.hosting', 'esn.tickets', 'esn.operations', 'esn.commerce'):
        await bot.load_extension(extension)
    bot.add_view(TicketPanel())
    bot.tree.add_command(PartnerGroup(partner_program))
    if os.getenv("STRIPE_POLLING_ENABLED") == "1":
        bot.loop.create_task(polling_loop(partner_program))
    logging.info("Loaded %s slash commands before sync", len(bot.tree.get_commands()))
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

@bot.tree.command(name="setup", description="Configure ESN Hosting Manager in Discord")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(staff_role="Role that can access support tickets", ticket_category="Category for private tickets")
async def setup(interaction: discord.Interaction, staff_role: discord.Role, ticket_category: discord.CategoryChannel):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
        return await luxury_send(interaction, "Manage Server permission required.", ephemeral=True)
    save_setting(interaction.guild.id, "staff_role", staff_role.id)
    save_setting(interaction.guild.id, "ticket_category", ticket_category.id)
    from esn import config
    config.put(interaction.guild.id, "staff_role", staff_role.id)
    config.put(interaction.guild.id, "ticket_category", ticket_category.id)
    await luxury_send(interaction, 
        f"**Manager configured!**\nStaff role: {staff_role.mention}\nTicket category: {ticket_category.name}\\nSettings survive restarts.",
        ephemeral=True,
    )

@bot.tree.command(name="ticketcategory", description="Set the category where support tickets are created")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(category="Discord category for new support tickets")
async def ticketcategory(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
        return await luxury_send(interaction, "Manage Server permission required.", ephemeral=True)
    save_setting(interaction.guild.id, "ticket_category", category.id)
    from esn import config
    config.put(interaction.guild.id, "ticket_category", category.id)
    embed = discord.Embed(title="ESN Hosting • Ticket Settings",
                          description=f"New support tickets will be created in **{category.name}**.\\nThis setting survives restarts.",
                          color=discord.Color.blurple())
    if interaction.guild.icon:
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text="ESN Hosting Manager", icon_url=interaction.guild.icon.url)
    await luxury_send(interaction, embed=embed, ephemeral=True)

@bot.tree.command(name="settings", description="View ESN Hosting Manager configuration")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def settings(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
        return await luxury_send(interaction, "Manage Server permission required.", ephemeral=True)
    guild = interaction.guild
    staff = guild.get_role(setting(guild.id, "staff_role", STAFF_ROLE_ID))
    category = guild.get_channel(setting(guild.id, "ticket_category", TICKET_CATEGORY_ID))
    await luxury_send(interaction, 
        f"**ESN Hosting Manager Settings**\nStaff: {staff.mention if staff else 'Not configured'}\nTickets: {category.name if category else 'Not configured'}",
        ephemeral=True,
    )

@bot.tree.command(name="hosting", description="View ESN Hosting Manager information")
async def hosting(interaction: discord.Interaction):
    await luxury_send(interaction, 
        "**ESN Hosting Manager MAX**\n"
        "Use /ticketpanel for support (staff only). Hosting control and Guardian modules are being developed.",
        ephemeral=True,
    )

@bot.tree.command(name="ticketpanel", description="Post the ESN Hosting ticket panel (staff only)")
@app_commands.guild_only()
async def ticketpanel(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
        return await luxury_send(interaction, "Staff only.", ephemeral=True)
    await luxury_send(interaction, "Ticket panel posted.", ephemeral=True)
    await interaction.channel.send(
        embed=luxury_embed(interaction, "Choose the service you need below. Our support team will assist you in a private ticket.", title="ESN HOSTING  |  CONCIERGE SUPPORT"),
        view=TicketPanel(),
    )

@bot.tree.command(name="ticketclose", description="Close the current Manager ticket (staff or ticket owner)")
@app_commands.guild_only()
async def ticketclose(interaction: discord.Interaction):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or not (channel.topic or "").startswith("esnhm-owner:"):
        return await luxury_send(interaction, "This isn't an ESN Hosting Manager ticket.", ephemeral=True)
    owner_id = int(channel.topic.split(":", 1)[1])
    member = interaction.user
    if not isinstance(member, discord.Member) or (member.id != owner_id and not is_staff(member)):
        return await luxury_send(interaction, "You cannot close this ticket.", ephemeral=True)
    await luxury_send(interaction, "Closing this ticket by archiving it. Staff can reopen it later.")
    await channel.edit(name=("archived-" + channel.name)[:100], topic=f"esnhm-archived:{owner_id}", reason=f"Ticket archived by {member.id}")
    await channel.set_permissions(member, send_messages=False) if member.id == owner_id else None

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in the server environment; never commit tokens.")
    bot.run(TOKEN)
