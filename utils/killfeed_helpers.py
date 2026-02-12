"""
Helper utilities for killfeed processing.
"""
import math
import re
import sqlite3
import time
import logging
from datetime import datetime
from typing import Tuple
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
    Format: Player "VictimName" (DEAD) (id=... pos=<...>) killed by Player "KillerName"
    
    Returns:
        Tuple: (killer_name, victim_name)
    """
    # Extract victim first (appears before "killed by", accounting for (DEAD) status and coordinates)
    victim = re.search(r'Player\s+"([^"]+)"\s+(?:\(DEAD\))?\s*\(id=[^)]+\s+pos=<[^>]+>\)\s+killed by', line)
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


def is_mam_device_event(line: str) -> bool:
    """
    Check if log line is a MAM device data event containing device ID and account UID.
    Formats: 
        - [MAM] :: [NetworkServer::CheckMAMData] :: device: ... | account: ... 
        - [MAM] :: [NetworkServer::RegisterMAMData] :: device: ... | account: ...
        - [MAM] :: [NetworkServer::RegisterMAMDataHelper] :: id1: ... | id2: ...
    
    Args:
        line: Log line to check
    
    Returns:
        Bool: True if this is a MAM device event
    """
    if "[MAM]" not in line:
        return False
    
    # Check for different MAM formats
    has_register = "[NetworkServer::RegisterMAMData]" in line or "[NetworkServer::RegisterMAMDataHelper]" in line or "[NetworkServer::CheckMAMData]" in line
    
    if not has_register:
        return False
    
    # Check for device indicators
    has_device = ("device:" in line and "account:" in line) or ("id1:" in line and "id2:" in line)
    
    return has_device


def extract_device_id_and_uid(line: str) -> tuple:
    """
    Extract device ID and account UID from a MAM log line.
    Formats:
        - [MAM] :: [NetworkServer::CheckMAMData] :: device: VUZwoETj2mkhZSZuUxOg5T8jwr0TrB4R_pt4klUoRio= | account: 383C4A0D1E702B6598B37338975EA3DB61DBC6D2 | time: 1077797
        - [MAM] :: [NetworkServer::RegisterMAMData] :: device: nwQBlewhhiL1eDq6FnyQ8z5-1IHvtOEcZfl32JItLhU= | account: 1F2D7D5BA6A2956E3D1343E44EBA4DD7941DD562 | time: 27250172
        - [MAM] :: [NetworkServer::RegisterMAMDataHelper] :: id1: nwQBlewhhiL1eDq6FnyQ8z5-1IHvtOEcZfl32JItLhU= | id2: 1F2D7D5BA6A2956E3D1343E44EBA4DD7941DD562 | time: 27250172
    
    Args:
        line: MAM log line
    
    Returns:
        Tuple: (device_id, uid) or (None, None) if extraction fails
    """
    try:
        device_id = None
        uid = None
        
        # Try standard format with device: and account:
        device_match = re.search(r'device:\s*([^\s|]+)', line)
        account_match = re.search(r'account:\s*([^\s|]+)', line)
        
        if device_match and account_match:
            device_id = device_match.group(1).strip()
            uid = account_match.group(1).strip()
        else:
            # Try RegisterMAMDataHelper format with id1: and id2:
            id1_match = re.search(r'id1:\s*([^\s|]+)', line)
            id2_match = re.search(r'id2:\s*([^\s|]+)', line)
            
            if id1_match and id2_match:
                device_id = id1_match.group(1).strip()
                uid = id2_match.group(1).strip()
        
        logger.debug(f"Extracted device_id: {device_id}, uid: {uid}")
        return device_id, uid
    except Exception as e:
        logger.error(f"Error extracting device ID and UID: {e}")
        return None, None


def extract_player_name_from_state_machine(line: str) -> str:
    """
    Extract player name from StateMachine log line.
    Format: [StateMachine]: Player PlayerName (dpnid ... uid ...)
    
    Args:
        line: StateMachine log line
    
    Returns:
        String: Player name or empty string if not found
    """
    try:
        match = re.search(r'\[StateMachine\]: Player\s+([^\s(]+)', line)
        if match:
            return match.group(1).strip()
    except Exception as e:
        logger.error(f"Error extracting player name from StateMachine: {e}")
    
    return ""


def extract_uid_from_connection_event(line: str) -> str:
    """
    Extract UID from player connection event line.
    Format: Player "PlayerName" (id=383C4A0D1E702B6598B37338975EA3DB61DBC6D2) has connected.
    Or: Player PlayerName (id=383C4A0D1E702B6598B37338975EA3DB61DBC6D2) has connected.
    
    Args:
        line: Connection event log line
    
    Returns:
        String: UID or empty string if not found
    """
    try:
        # Try to match with quoted name first
        match = re.search(r'\(id=([A-F0-9]+)\)', line)
        if match:
            uid = match.group(1).strip()
            player_match = re.search(r'Player\s+"?([^"()]+)"?\s*\(', line)
            if player_match:
                return uid
    except Exception as e:
        logger.error(f"Error extracting UID from connection event: {e}")
    
    return ""


def get_player_from_connection_event(line: str) -> Tuple[str, str]:
    """
    Extract both player name and UID from connection event.
    Format: Player Tylerj85 (id=383C4A0D1E702B6598B37338975EA3DB61DBC6D2) has connected.
    
    Returns:
        Tuple: (player_name, uid) or ("", "") if not found
    """
    try:
        # Extract UID from (id=...)
        uid_match = re.search(r'\(id=([A-F0-9]+)\)', line)
        uid = uid_match.group(1).strip() if uid_match else ""
        
        # Extract player name - matches "Player PlayerName (id="
        player_match = re.search(r'Player\s+([^\s(]+)\s*\(id=', line)
        player = player_match.group(1).strip() if player_match else ""
        
        return player, uid
    except Exception as e:
        logger.error(f"Error extracting player and UID from connection event: {e}")
    
    return "", ""


def extract_uid_from_state_machine_event(line: str) -> Tuple[str, str]:
    """
    Extract player name and UID from StateMachine log line.
    Format: [StateMachine]: Player Anarchy Dubz966 (dpnid 26602006 uid 1F2D7D5BA6A2956E3D1343E44EBA4DD7941DD562) Entering ...
    
    Returns:
        Tuple: (player_name, uid) or ("", "") if not found
    """
    try:
        # Extract player name and uid from StateMachine line
        # Format: [StateMachine]: Player PlayerName (dpnid ... uid UID)
        # Using (.+?) for non-greedy match to handle player names with spaces
        match = re.search(r'\[StateMachine\]: Player\s+(.+?)\s+\(dpnid\s+\d+\s+uid\s+([A-F0-9]*)\)', line)
        
        if match:
            player = match.group(1).strip()
            uid = match.group(2).strip() if match.group(2) else ""
            return player, uid
    except Exception as e:
        logger.error(f"Error extracting UID from StateMachine event: {e}")
    
    return "", ""


def extract_player_and_uid_from_char_debug(line: str) -> Tuple[str, str, str]:
    """
    Extract player name, UID, and DPNID from CHAR_DEBUG log line.
    Format 1 (with name): CHAR_DEBUG - SAVE ... player PlayerName (dpnid = 26602006)
    Format 2 (UID only): CHAR_DEBUG - EXIT ... player 1F2D7D5BA6A2956E3D1343E44EBA4DD7941DD562 (dpnid = 26602006)
    
    Returns:
        Tuple: (player_name, uid, dpnid) or ("", "", "") if not found
    """
    try:
        # Extract DPNID (always present)
        dpnid_match = re.search(r'dpnid\s*=\s*(\d+)', line)
        dpnid = dpnid_match.group(1).strip() if dpnid_match else ""
        
        # Check for UID format (40-char hex string)
        uid_match = re.search(r'player\s+([A-F0-9]{40})\s+\(dpnid', line)
        if uid_match:
            uid = uid_match.group(1).strip()
            return "", uid, dpnid  # Only UID and DPNID available
        
        # Check for player name format
        name_match = re.search(r'player\s+([^\s(]+)\s+\(dpnid', line)
        if name_match:
            player = name_match.group(1).strip()
            return player, "", dpnid  # Player name and DPNID available
    except Exception as e:
        logger.error(f"Error extracting from CHAR_DEBUG: {e}")
    
    return "", "", ""


def extract_uid_from_disconnect(line: str) -> str:
    """
    Extract UID from Disconnect log line.
    Format: [Disconnect]: Finish script disconnect DPNID (1F2D7D5BA6A2956E3D1343E44EBA4DD7941DD562)
    
    Returns:
        String: UID or empty string if not found
    """
    try:
        # Match UID in parentheses after disconnect message
        uid_match = re.search(r'\([A-F0-9]{40}\)', line)
        if uid_match:
            uid = uid_match.group(0).strip('()')
            return uid
    except Exception as e:
        logger.error(f"Error extracting UID from Disconnect: {e}")
    
    return ""
