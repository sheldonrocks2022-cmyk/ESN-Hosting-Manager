"""Customer ticket workflows: claim, priority, transcript, archive and reopen."""
import io
import discord
from discord import app_commands
from discord.ext import commands
from . import config

def ticket_owner(channel):
    if not isinstance(channel,discord.TextChannel): return None
    topic=channel.topic or ""
    if not topic.startswith("esnhm-owner:"): return None
    try: return int(topic.split(":",1)[1].split(";",1)[0])
    except ValueError: return None

class Tickets(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def guard(self,interaction,staff_only=True):
        owner=ticket_owner(interaction.channel)
        if owner is None:
            await interaction.response.send_message("Use this inside an ESN Hosting Manager ticket.",ephemeral=True)
            return False
        if staff_only and not config.role_allowed(interaction.user):
            await interaction.response.send_message("Staff only.",ephemeral=True)
            return False
        if not staff_only and not (config.role_allowed(interaction.user) or owner==interaction.user.id):
            await interaction.response.send_message("Not your ticket.",ephemeral=True)
            return False
        return True

    @app_commands.command(name="ticketclaim",description="Claim the current support ticket")
    @app_commands.guild_only()
    async def ticketclaim(self,interaction:discord.Interaction):
        if not await self.guard(interaction): return
        config.put(interaction.guild.id,f"claim:{interaction.channel.id}",interaction.user.id)
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}.")

    @app_commands.command(name="ticketpriority",description="Set ticket priority")
    @app_commands.guild_only()
    @app_commands.choices(priority=[app_commands.Choice(name=p,value=p) for p in ("low","normal","high","urgent")])
    async def ticketpriority(self,interaction:discord.Interaction,priority:app_commands.Choice[str]):
        if not await self.guard(interaction): return
        config.put(interaction.guild.id,f"priority:{interaction.channel.id}",priority.value)
        await interaction.response.send_message(f"Priority set to **{priority.name}**.")

    @app_commands.command(name="tickettransfer",description="Transfer ticket claim to another staff member")
    @app_commands.guild_only()
    async def tickettransfer(self,interaction:discord.Interaction,staff:discord.Member):
        if not await self.guard(interaction): return
        if not config.role_allowed(staff):
            return await interaction.response.send_message("Choose a configured staff member.",ephemeral=True)
        config.put(interaction.guild.id,f"claim:{interaction.channel.id}",staff.id)
        await interaction.response.send_message(f"Ticket transferred to {staff.mention}.")

    @app_commands.command(name="tickettranscript",description="Export the current ticket messages")
    @app_commands.guild_only()
    async def tickettranscript(self,interaction:discord.Interaction):
        if not await self.guard(interaction,staff_only=False): return
        await interaction.response.defer(ephemeral=True)
        lines=[]
        async for msg in interaction.channel.history(limit=500,oldest_first=True):
            lines.append(f"[{msg.created_at.isoformat()}] {msg.author} ({msg.author.id}): {msg.clean_content}")
        content="\n".join(lines) or "No messages."
        output=io.BytesIO(content.encode("utf-8"))
        await interaction.followup.send(file=discord.File(output,filename=f"ticket-{interaction.channel.id}.txt"),ephemeral=True)

    @app_commands.command(name="ticketarchive",description="Archive a ticket without deleting its messages")
    @app_commands.guild_only()
    async def ticketarchive(self,interaction:discord.Interaction):
        if not await self.guard(interaction): return
        channel=interaction.channel
        owner_id=ticket_owner(channel)
        owner=interaction.guild.get_member(owner_id)
        await interaction.response.send_message("Ticket archived. Staff can reopen it with /ticketreopen.")
        changes={interaction.guild.default_role:discord.PermissionOverwrite(view_channel=False)}
        if owner: changes[owner]=discord.PermissionOverwrite(view_channel=True,send_messages=False,read_message_history=True)
        for role,permissions in changes.items(): await channel.set_permissions(role,overwrite=permissions)
        await channel.edit(name=("archived-"+channel.name)[:100],topic=f"esnhm-archived:{owner_id}")

    @app_commands.command(name="ticketreopen",description="Reopen an archived ticket")
    @app_commands.guild_only()
    async def ticketreopen(self,interaction:discord.Interaction):
        channel=interaction.channel
        if not isinstance(channel,discord.TextChannel) or not (channel.topic or "").startswith("esnhm-archived:"):
            return await interaction.response.send_message("Not an archived Manager ticket.",ephemeral=True)
        if not config.role_allowed(interaction.user):
            return await interaction.response.send_message("Staff only.",ephemeral=True)
        owner_id=int(channel.topic.split(":",1)[1])
        owner=interaction.guild.get_member(owner_id)
        if owner: await channel.set_permissions(owner,view_channel=True,send_messages=True,read_message_history=True)
        await channel.edit(name=channel.name.removeprefix("archived-"),topic=f"esnhm-owner:{owner_id}")
        await interaction.response.send_message("Ticket reopened.")

    @app_commands.command(name="ticketstats",description="Show Manager ticket counts")
    @app_commands.guild_only()
    async def ticketstats(self,interaction:discord.Interaction):
        if not config.role_allowed(interaction.user):
            return await interaction.response.send_message("Staff only.",ephemeral=True)
        channels=[c for c in interaction.guild.text_channels if (c.topic or "").startswith("esnhm-")]
        opened=sum(ticket_owner(c) is not None for c in channels)
        await interaction.response.send_message(f"**Tickets:** {opened} open, {len(channels)-opened} archived.",ephemeral=True)

async def setup(bot): await bot.add_cog(Tickets(bot))
