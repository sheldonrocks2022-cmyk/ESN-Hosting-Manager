"""ESN Hosting premium response system for all slash-command modules."""
import discord

BRAND = 0xD5AD65
ERROR = 0xD95565

def luxury_embed(interaction, content="", *, title=None, error=False):
    guild = interaction.guild
    icon = guild.icon.url if guild and guild.icon else None
    embed = discord.Embed(
        title=title or ("ESN HOSTING  |  NOTICE" if error else "ESN HOSTING  |  CONTROL CENTER"),
        description=str(content or "Operation completed."),
        color=ERROR if error else BRAND,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(name=(guild.name if guild else "ESN Hosting") + "  •  Official Services", icon_url=icon)
    if icon:
        embed.set_thumbnail(url=icon)
    embed.set_footer(text="ESN HOSTING  •  PRIVATE INFRASTRUCTURE  •  PREMIUM SUPPORT", icon_url=icon)
    return embed

async def luxury_send(interaction, content=None, *, embed=None, embeds=None, **kwargs):
    if content is not None and embed is None and embeds is None:
        error = any(word in str(content).lower() for word in (
            "required", "not configured", "not found", "invalid", "unable",
            "permission", "denied", "not your", "staff only", "failed", "error"))
        embed = luxury_embed(interaction, content, error=error)
        content = None
    return await interaction.response.send_message(content=content, embed=embed, embeds=embeds, **kwargs)

async def luxury_followup(interaction, content=None, *, embed=None, embeds=None, **kwargs):
    if content is not None and embed is None and embeds is None:
        embed = luxury_embed(interaction, content)
        content = None
    return await interaction.followup.send(content=content, embed=embed, embeds=embeds, **kwargs)
