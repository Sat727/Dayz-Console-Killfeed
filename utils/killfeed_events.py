"""
Event handling and Discord embed creation for killfeed.
"""
import re
import discord
import logging
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)


async def create_pvp_kill_embed(
    killer: str,
    victim: str,
    weapon: str,
    distance: float,
    bodypart: str,
    timestamp: str,
    killer_stats: dict,
    victim_stats: dict,
    timealive_str: str,
    dayz_map_url: str,
    killer_coords: str = "",
    victim_coords: str = "",
    enable_coord_links: bool = False
) -> discord.Embed:
    """
    Create a Discord embed for a PvP kill event.
    
    Args:
        killer: Name of the killer
        victim: Name of the victim
        weapon: Weapon used
        distance: Distance in meters
        bodypart: Body part hit
        timestamp: Discord timestamp
        killer_stats: Dict with killer's stats (kills, deaths, rank, killstreak)
        victim_stats: Dict with victim's stats (kills, deaths, rank, deathstreak)
        timealive_str: Formatted time alive string
        dayz_map_url: Base map URL for coordinate links
    
    Returns:
        discord.Embed: The embed for the kill
    """
    try:
        # Safely get stats with defaults for new/unknown players
        killer_kills = killer_stats.get('kills', 0)
        killer_deaths = killer_stats.get('deaths', 0)
        victim_kills = victim_stats.get('kills', 0)
        victim_deaths = victim_stats.get('deaths', 0)
        
        killer_kd = round(killer_kills / killer_deaths, 2) if killer_deaths > 0 else float(killer_kills)
        victim_kd = round(victim_kills / victim_deaths, 2) if victim_deaths > 0 else float(victim_kills)
        
        # Get other stats with safe defaults
        killer_rank = killer_stats.get('rank', 0)
        killer_killstreak = killer_stats.get('killstreak', 0)
        victim_rank = victim_stats.get('rank', 0)
        victim_deathstreak = victim_stats.get('deathstreak', 0)
        
        # Build killer/victim names with optional coordinate links
        killer_name = killer
        victim_name = victim
        if enable_coord_links:
            if killer_coords:
                killer_name = f"[{killer}]({dayz_map_url}{killer_coords})"
            if victim_coords:
                victim_name = f"[{victim}]({dayz_map_url}{victim_coords})"
        
        description = f"""**{killer_name}** killed **{victim_name}**

**Weapon**: `{weapon}` ({distance}m) {'hit' if bodypart else ''} {bodypart}
**{killer}'s Stats**:
K/D - {killer_kd} | {killer_deaths} Death{'s' if killer_deaths > 1 else ''} {killer_kills} Kill{'s' if killer_kills > 1 else ''} | Ranked #{killer_rank} Kills
Killstreak - {killer_killstreak}
**{victim}'s Stats:**
K/D - {victim_kd} | {victim_deaths} Death{'s' if victim_deaths > 1 else ''} {victim_kills} Kill{'s' if victim_kills > 1 else ''} | Ranked #{victim_rank} Deaths
DeathStreak - {victim_deathstreak}
{'Time Alive - ' if int(int(victim_stats.get('alive_seconds', 0)) + victim_stats.get('alive_hours', 0) + victim_stats.get('alive_minutes', 0) + victim_stats.get('alive_days', 0)) > 0 else ''}{timealive_str}
"""
        
        embed = discord.Embed(
            title=f"PvP Kill | {timestamp}",
            description=description,
            color=0xE40000,
        ).set_thumbnail(url=Config.EMBED_IMAGE).set_footer(text=Config.EMBED_FOOTER, icon_url=Config.EMBED_FOOTER_IMAGE)
        
        return embed
    except Exception as e:
        logger.error(f"Error creating PvP kill embed: {e}")
        raise


async def create_suicide_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for suicide event."""
    return discord.Embed(
        title=f"Suicide | {timestamp}",
        description=f"**{victim}** committed suicide",
        color=0xE40000,
    )


async def create_explosion_embed(victim: str, explosion_type: str, timestamp: str) -> discord.Embed:
    """Create embed for explosion death event."""
    return discord.Embed(
        title=f"Exploded | {timestamp}",
        description=f"**{victim}** died from explosion ({explosion_type})",
        color=0xE40000,
    )


async def create_bleed_out_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for bleed out death event."""
    return discord.Embed(
        title=f"Bled Out | {timestamp}",
        description=f"**{victim}** bled out",
        color=0xE40000,
    )


async def create_wolf_kill_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for wolf kill event."""
    return discord.Embed(
        title=f"Wolf Kill | {timestamp}",
        description=f"**{victim}** was killed by a Wolf",
        color=0xE40000,
    )


async def create_bear_kill_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for bear kill event."""
    return discord.Embed(
        title=f"Bear Kill | {timestamp}",
        description=f"**{victim}** was killed by a Bear",
        color=0xE40000,
    )


async def create_fall_death_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for fall death event."""
    return discord.Embed(
        title=f"Fall Death | {timestamp}",
        description=f"**{victim}** fell to their death",
        color=0xE40000,
    )


async def create_generic_death_embed(victim: str, timestamp: str) -> discord.Embed:
    """Create embed for generic death event."""
    return discord.Embed(
        title=f"Died | {timestamp}",
        description=f"**{victim}** died",
        color=0xE40000,
    )


def is_suicide_event(line: str) -> bool:
    """Check if log line represents a suicide."""
    return "committed suicide" in line


def is_explosion_event(line: str) -> bool:
    """Check if log line represents an explosion death."""
    return "hit by explosion" in line


def is_pvp_kill_event(line: str) -> bool:
    """Check if log line represents a PvP kill."""
    return "killed by Player" in line


def is_bleed_out_event(line: str) -> bool:
    """Check if log line represents bleeding out."""
    return "bled out" in line


def is_wolf_kill_event(line: str) -> bool:
    """Check if log line represents a wolf kill."""
    return any(wolf in line for wolf in ["Animal_CanisLupus_Grey", "Animal_CanisLupus_White"])


def is_bear_kill_event(line: str) -> bool:
    """Check if log line represents a bear kill."""
    return any(bear in line for bear in ["Animal_UrsusArctos", "Brown Bear"])


def is_fall_death_event(line: str) -> bool:
    """Check if log line represents a fall death."""
    return "hit by FallDamage" in line


def is_death_event(line: str) -> bool:
    """Check if log line represents a death (generic)."""
    return "(DEAD)" in line or "died" in line


def extract_explosion_type(line: str) -> str:
    """Extract explosion type from log line."""
    match = re.search(r"\[HP: 0\] hit by explosion \((.*)\)", line)
    return match.group(1) if match else "Unknown"


async def create_player_connected_embed(player: str, timestamp: str) -> discord.Embed:
    """Create embed for player connection event."""
    return discord.Embed(
        title=f"Player Connected | {timestamp}",
        description=f"**{player}** connected to the server",
        color=0x00FF00,
    )


async def create_player_disconnected_embed(player: str, timestamp: str) -> discord.Embed:
    """Create embed for player disconnection event."""
    return discord.Embed(
        title=f"Player Disconnected | {timestamp}",
        description=f"**{player}** disconnected from the server",
        color=0xFFFF00,
    )



def is_player_connected_event(line: str) -> bool:
    """Check if log line represents a player connection."""
    return "is connected" in line and "(id=" in line and "has been disconnected" not in line


def is_player_disconnected_event(line: str) -> bool:
    """Check if log line represents a player disconnection."""
    return "has been disconnected" in line
