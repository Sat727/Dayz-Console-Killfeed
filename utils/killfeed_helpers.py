"""
Helper utilities for killfeed processing.
"""
import math
import re
import sqlite3
import time
import logging
from datetime import datetime
import pytz
import aiofiles

logger = logging.getLogger(__name__)


def calculate_distance(x1: float, z1: float, x2: float, z2: float) -> float:
    """
    Calculate Euclidean distance between two coordinates.
    
    Args:
        x1, z1: First coordinate pair
        x2, z2: Second coordinate pair
    
    Returns:
        Float: Distance between the two points
    """
    return math.sqrt((x1 - x2) ** 2 + (z1 - z2) ** 2)


async def time_func(timestamp: str) -> str:
    """
    Convert server timestamp to Discord timestamp format (US/Eastern timezone).
    
    Args:
        timestamp: Time string in format "HH:MM:SS"
    
    Returns:
        String: Discord timestamp format
    """
    parts = timestamp.split(':')
    if len(parts[2]) == 1:
        timestamp = f"{parts[0]}:{parts[1]}:{parts[2].zfill(2)}"
    
    utc_now = datetime.now(pytz.utc)
    est_timezone = pytz.timezone('US/Eastern')
    est_time = datetime.strptime(f"{utc_now.strftime('%Y-%m-%d')} {timestamp}", '%Y-%m-%d %H:%M:%S')
    est_time = est_timezone.localize(est_time)
    utc_time = est_time.astimezone(pytz.utc)
    est_time = utc_time.astimezone(est_timezone)
    
    return f'<t:{int(est_time.timestamp())}>'


def format_time_alive(seconds: int, minutes: int, hours: int, days: int) -> str:
    """
    Format time alive into a human-readable string.
    
    Args:
        seconds: Total seconds
        minutes: Total minutes
        hours: Total hours
        days: Total days
    
    Returns:
        String: Formatted time alive string
    """
    timealivestr = ''
    if days > 0:
        timealivestr += f'{days} Day{"s" if days > 1 else ""}, '
    if hours > 0:
        timealivestr += f'{hours} Hour{"s" if hours > 1 else ""}, '
    if minutes > 0:
        timealivestr += f'{minutes} Minute{"s" if minutes > 1 else ""}, '
    if int(seconds) > 0:
        timealivestr += f'{int(seconds)} Second{"s" if int(seconds) > 1 else ""}'
    
    return timealivestr


def extract_coordinates(line: str) -> tuple:
    """
    Extract X and Z coordinates from a log line.
    
    Args:
        line: Log line containing position data
    
    Returns:
        Tuple: (x, z) coordinates or (None, None) if not found
    """
    match = re.search(r'pos=<([\d.]+), [\d.]+, ([\d.]+)>', line)
    if match:
        return map(float, match.groups())
    return None, None


def extract_player_name(line: str) -> str:
    """Extract player name from log line. Matches: Player "Name"(id=...) or Player "Name" (id=...)"""
    match = re.search(r'Player\s+"([^"]+)"', line)
    if match:
        return str(match.group(1)).strip()
    return ""


def extract_killer_victim(line: str) -> tuple:
    """
    Extract both killer and victim names from a kill event line.
    Format: Player "VictimName" killed by Player "KillerName"
    
    Returns:
        Tuple: (killer_name, victim_name)
    """
    # Extract victim first (appears before "killed by")
    victim = re.search(r'Player\s+"([^"]+)"\s+killed by', line)
    victim = victim.group(1) if victim else ""
    
    # Extract killer (after "killed by Player")
    killer = re.search(r'killed by Player\s+"([^"]+)"', line)
    killer = killer.group(1) if killer else ""
    
    return killer, victim


def extract_timestamp(line: str) -> str:
    """Extract HH:MM:SS timestamp from log line."""
    match = re.search(r"(\d+:\d+:\d+)", line)
    return match.group(1) if match else ""


def extract_distance(line: str) -> float:
    """Extract distance in meters from log line."""
    try:
        match = re.search(r"from ([0-9.]+) meters", line)
        return round(float(match.group(1)), 2) if match else 0.0
    except (AttributeError, ValueError):
        return 0.0


def extract_weapon(line: str, weapons_data: dict = None) -> str:
    """
    Extract weapon name from log line and map to friendly name if possible.
    
    Args:
        line: Log line containing weapon info
        weapons_data: Optional dict of weapon mappings
    
    Returns:
        String: Weapon name
    """
    weapon_match = re.search(r" with (.*) from", line) or re.search(r"with (.*)", line)
    weapon = weapon_match.group(1) if weapon_match else "Unknown"
    
    if weapons_data and weapon in weapons_data.get('data', {}):
        weapon = weapons_data['data'][weapon]
    
    return weapon


def extract_bodypart(line: str) -> str:
    """Extract body part hit from log line."""
    match = re.search(r'into ([^(]+)', line)
    return match.group(1) if match else ""


def extract_coordinates_from_line(line: str) -> list:
    """Extract all coordinate pairs from a log line."""
    return re.findall(r'pos=<([^>]+)>', line)


def format_coordinates(coords_str: str) -> str:
    """
    Format coordinates for URL encoding.
    Removes commas and decimal places.
    """
    formatted = re.sub(r',\s*', ';', coords_str)
    formatted = re.sub(r'\.\d+', '', formatted)
    return formatted


async def new_logfile(filepath: str) -> bool:
    """
    Check if the log file is newly created (contains only one AdminLog entry).
    
    Args:
        filepath: Path to the log file
    
    Returns:
        Bool: True if new logfile, False otherwise
    """
    try:
        async with aiofiles.open(filepath, "r") as f:
            text = await f.read()
            logs = len(re.findall("AdminLog", text))
        return logs == 1
    except Exception as e:
        logger.error(f"Error checking logfile: {e}")
        return False
