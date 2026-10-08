"""ESN Hosting Manager MAX — initial functional foundation."""
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID") or "0")
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID") or "0")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild or any(role.id == STAFF_ROLE_ID for role in member.roles)

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
            return await interaction.response.send_message("Use this panel in a server.", ephemeral=True)
        if not TICKET_CATEGORY_ID:
            return await interaction.response.send_message("Ticket category is not configured.", ephemeral=True)
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("Configured ticket category was not found.", ephemeral=True)
        staff_role = guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None
        if staff_role is None:
            return await interaction.response.send_message("Staff role is not configured.", ephemeral=True)
        # One open ticket per user, preventing duplicate channels and spam.
        for channel in category.text_channels:
            if channel.topic == f"esnhm-owner:{interaction.user.id}":
                return await interaction.response.send_message(f"You already have a ticket: {channel.mention}", ephemeral=True)
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
            await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I need Manage Channels and permission to view the ticket category.", ephemeral=True)

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    logging.info("Connected as %s", bot.user)

@bot.event
async def setup_hook():
    bot.add_view(TicketPanel())
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

@bot.tree.command(name="hosting", description="View ESN Hosting Manager information")
async def hosting(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**ESN Hosting Manager MAX**\n"
        "Use /ticketpanel for support (staff only). Hosting control and Guardian modules are being developed.",
        ephemeral=True,
    )

@bot.tree.command(name="ticketpanel", description="Post the ESN Hosting ticket panel (staff only)")
@app_commands.guild_only()
async def ticketpanel(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
        return await interaction.response.send_message("Staff only.", ephemeral=True)
    await interaction.response.send_message("Ticket panel posted.", ephemeral=True)
    await interaction.channel.send(
        embed=discord.Embed(
            title="🎟️ ESN Hosting Support",
            description="Select a category below to open a private support ticket.",
            color=discord.Color.from_rgb(0, 190, 220),
        ),
        view=TicketPanel(),
    )

@bot.tree.command(name="ticketclose", description="Close the current Manager ticket (staff or ticket owner)")
@app_commands.guild_only()
async def ticketclose(interaction: discord.Interaction):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or not (channel.topic or "").startswith("esnhm-owner:"):
        return await interaction.response.send_message("This isn't an ESN Hosting Manager ticket.", ephemeral=True)
    owner_id = int(channel.topic.split(":", 1)[1])
    member = interaction.user
    if not isinstance(member, discord.Member) or (member.id != owner_id and not is_staff(member)):
        return await interaction.response.send_message("You cannot close this ticket.", ephemeral=True)
    await interaction.response.send_message("Closing this ticket. Messages will be deleted with the channel.")
    await channel.delete(reason=f"Ticket closed by {member.id}")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in the server environment; never commit tokens.")
    bot.run(TOKEN)
