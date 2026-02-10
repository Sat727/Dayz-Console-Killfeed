"""
Consolidated database utilities for killfeed operations.
Uses a single database with multiple tables instead of separate database files.
"""
import sqlite3
import logging
import time
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global database path
KILLFEED_DB_PATH = "db/killfeed.db"


def get_connection(db_path: str = KILLFEED_DB_PATH) -> sqlite3.Connection:
    """Get a database connection."""
    return sqlite3.connect(db_path)


def initialize_master_db(db_path: str = KILLFEED_DB_PATH) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    Initialize the master database with all required tables.
    
    Args:
        db_path: Path to the master database
    
    Returns:
        Tuple: (connection, cursor)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Player statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT UNIQUE NOT NULL,
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0,
                alivetime INTEGER DEFAULT 0,
                deathstreak INTEGER DEFAULT 0,
                killstreak INTEGER DEFAULT 0,
                dcid INTEGER DEFAULT 0,
                money INTEGER DEFAULT 0,
                bounty INTEGER DEFAULT 0,
                device_id TEXT DEFAULT NULL,
                uid TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add uid column if it doesn't exist (for existing databases)
        cursor.execute("PRAGMA table_info(stats)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'uid' not in columns:
            try:
                cursor.execute("ALTER TABLE stats ADD COLUMN uid TEXT DEFAULT NULL")
                conn.commit()
                logger.info("Added 'uid' column to stats table")
            except sqlite3.OperationalError as e:
                logger.debug(f"Column 'uid' already exists or operation failed: {e}")
        
        # Activity data series tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_series_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name TEXT UNIQUE NOT NULL,
                activedata TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                counter_name TEXT UNIQUE NOT NULL,
                activedata INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Region table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS region (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                x REAL,
                z REAL,
                radius REAL,
                channelid INTEGER,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Codes/Batch table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                data TEXT,
                redeemed BOOLEAN DEFAULT 0,
                user TEXT DEFAULT NULL,
                batchid TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Servers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Device ID bans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deviceid_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                device_id TEXT UNIQUE NOT NULL,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Template/Config table (now supports multiple servers)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                category TEXT NOT NULL,
                channelid INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(server_id, category)
            )
        """)
        
        # Add server_id column to existing config table if it doesn't have it
        cursor.execute("PRAGMA table_info(config)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'server_id' not in columns:
            try:
                cursor.execute("ALTER TABLE config ADD COLUMN server_id TEXT DEFAULT ''")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists or other error
        
        # Server-specific logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                log_type TEXT,
                log_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Players table for player-specific settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                logconfig_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info(f"Master database initialized at {db_path}")
        return conn, cursor
    except Exception as e:
        logger.error(f"Failed to initialize master database: {e}")
        raise


def initialize_stats_db(db_path: str = KILLFEED_DB_PATH) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    Initialize and return the stats database connection and cursor.
    Maintains backward compatibility with original function signature.
    
    Args:
        db_path: Path to the database (uses KILLFEED_DB_PATH by default)
    
    Returns:
        Tuple: (connection, cursor)
    """
    return initialize_master_db(db_path)


def initialize_activity_db(db_path: str = KILLFEED_DB_PATH) -> sqlite3.Connection:
    """
    Initialize activity data tables.
    Maintains backward compatibility with original function signature.
    
    Args:
        db_path: Path to the database
        
    Returns:
        Connection object
    """
    conn, _ = initialize_master_db(db_path)
    
    # Initialize activity series
    series_names = ['data', 'onlinecount', 'deathdata', 'killdata']
    for series in series_names:
        init_activity_series(series, '0;0;0;0;0;0;0;0;0;0;0;0', db_path)
    
    # Initialize activity counters
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO activity_counters (counter_name, activedata) VALUES (?, ?)",
        ('killcount', 0)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO activity_counters (counter_name, activedata) VALUES (?, ?)",
        ('deathcount', 0)
    )
    conn.commit()
    conn.close()
    
    return get_connection(db_path)


def init_activity_series(series_name: str, initial_value: str = '', db_path: str = KILLFEED_DB_PATH) -> None:
    """Initialize an activity series entry."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO activity_series_data (series_name, activedata) VALUES (?, ?)",
            (series_name, initial_value)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing series {series_name}: {e}")


def check_user_exists(cursor, player: str, stats_conn: sqlite3.Connection) -> None:
    """
    Check if a player exists in stats table. Create entry if not (case-insensitive lookup).
    
    Args:
        cursor: Database cursor
        player: Player name
        stats_conn: Database connection
    """
    try:
        cursor.execute("SELECT * FROM stats WHERE user = ? COLLATE NOCASE", (player,))
        result = cursor.fetchall()
        
        if not result or result == [()]:
            current_time = int(time.mktime(datetime.now().timetuple()))
            cursor.execute(
                "INSERT INTO stats (user, kills, deaths, alivetime, killstreak, deathstreak, dcid, money, bounty, device_id) "
                "VALUES (?, 0, 0, ?, 0, 0, 0, 0, 0, NULL)",
                (player, current_time)
            )
            stats_conn.commit()
            logger.debug(f"Initialized player: {player}")
    except Exception as e:
        logger.error(f"Error checking user existence for {player}: {e}")


def update_kill_stats(cursor, killer: str, victim: str, stats_conn: sqlite3.Connection) -> None:
    """
    Update kill and death statistics for a PvP kill (case-insensitive lookup).
    NOTE: Does NOT update alivetime on death - alivetime is only set when player first joins.
    
    Args:
        cursor: Database cursor
        killer: Player who killed
        victim: Player who died
        stats_conn: Database connection
    """
    try:
        cursor.execute(
            "UPDATE stats SET kills = kills + 1, killstreak = killstreak + 1, deathstreak = 0 WHERE user = ? COLLATE NOCASE",
            (killer,)
        )
        cursor.execute(
            "UPDATE stats SET deaths = deaths + 1, killstreak = 0, deathstreak = deathstreak + 1 WHERE user = ? COLLATE NOCASE",
            (victim,)
        )
        
        stats_conn.commit()
        logger.debug(f"Updated stats: {killer} killed {victim}")
    except Exception as e:
        logger.error(f"Error updating kill stats: {e}")


def update_death_stats(cursor, victim: str, stats_conn: sqlite3.Connection) -> None:
    """
    Update death statistics for a non-PvP death (case-insensitive lookup).
    
    Args:
        cursor: Database cursor
        victim: Player who died
        stats_conn: Database connection
    """
    try:
        cursor.execute(
            "UPDATE stats SET deaths = deaths + 1, killstreak = 0, deathstreak = deathstreak + 1 WHERE user = ? COLLATE NOCASE",
            (victim,)
        )
        
        stats_conn.commit()
        logger.debug(f"Updated death stats: {victim}")
    except Exception as e:
        logger.error(f"Error updating death stats: {e}")


def get_player_stats(cursor, player: str) -> Dict[str, Any]:
    """
    Retrieve player statistics (case-insensitive lookup).
    
    Args:
        cursor: Database cursor
        player: Player name
    
    Returns:
        Dict: Player statistics or empty dict if not found
    """
    try:
        result = cursor.execute(
            "SELECT p1.*, (SELECT COUNT(*) FROM stats p2 WHERE p2.kills > p1.kills) as KillRank FROM stats p1 WHERE user = ? COLLATE NOCASE",
            (player,)
        ).fetchall()
        
        if result:
            return {
                'user': result[0][1],  # Adjusted for new schema with id column
                'kills': result[0][2],
                'deaths': result[0][3],
                'alivetime': result[0][4],
                'killstreak': result[0][6],
                'deathstreak': result[0][5],
                'rank': result[0][11] if result[0][11] > 0 else 1
            }
        return {}
    except Exception as e:
        logger.error(f"Error retrieving stats for {player}: {e}")
        return {}


def update_series(table_name: str, value: int, db_path: str = KILLFEED_DB_PATH) -> None:
    """
    Update activity series data (rolling window of stats).
    
    Args:
        table_name: Name of the series to update
        value: Value to append to series
        db_path: Path to database
    """
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT activedata FROM activity_series_data WHERE series_name = ?", (table_name,))
        result = cursor.fetchone()
        
        if result:
            current = result[0]
            history = current.split(';')[1:] if current else []
            history.append(str(value))
            result_str = ';'.join([''] + history)
            
            cursor.execute("UPDATE activity_series_data SET activedata = ?, updated_at = CURRENT_TIMESTAMP WHERE series_name = ?", (result_str, table_name))
        else:
            result_str = ';' + str(value)
            cursor.execute("INSERT INTO activity_series_data (series_name, activedata) VALUES (?, ?)", (table_name, result_str))
        
        conn.commit()
        conn.close()
        logger.debug(f"Updated series {table_name} with value {value}")
    except Exception as e:
        logger.error(f"Error updating series {table_name}: {e}")


def increment_activity_counters(kills: int, deaths: int, db_path: str = KILLFEED_DB_PATH) -> None:
    """
    Increment global kill and death counters.
    
    Args:
        kills: Number of kills to add
        deaths: Number of deaths to add
        db_path: Path to database
    """
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        if kills > 0:
            cursor.execute(
                "UPDATE activity_counters SET activedata = activedata + ?, updated_at = CURRENT_TIMESTAMP WHERE counter_name = ?",
                (kills, 'killcount')
            )
        if deaths > 0:
            cursor.execute(
                "UPDATE activity_counters SET activedata = activedata + ?, updated_at = CURRENT_TIMESTAMP WHERE counter_name = ?",
                (deaths, 'deathcount')
            )
        
        conn.commit()
        conn.close()
        logger.debug(f"Incremented counters: {kills} kills, {deaths} deaths")
    except Exception as e:
        logger.error(f"Error incrementing activity counters: {e}")


def get_total_kills(db_path: str = KILLFEED_DB_PATH) -> int:
    """Get total kills from database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        result = cursor.execute("SELECT activedata FROM activity_counters WHERE counter_name = ?", ('killcount',)).fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting total kills: {e}")
        return 0


def get_total_deaths(db_path: str = KILLFEED_DB_PATH) -> int:
    """Get total deaths from database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        result = cursor.execute("SELECT activedata FROM activity_counters WHERE counter_name = ?", ('deathcount',)).fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting total deaths: {e}")
        return 0


# Region functions
def insert_region(x: float, z: float, radius: float, channelid: int, name: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a region into the database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO region (x, z, radius, channelid, name) VALUES (?, ?, ?, ?, ?)",
            (x, z, radius, channelid, name)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Inserted region: {name}")
    except Exception as e:
        logger.error(f"Error inserting region: {e}")


def get_regions(db_path: str = KILLFEED_DB_PATH):
    """Get all regions."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT x, z, radius, channelid, name FROM region")
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting regions: {e}")
        return []


# Code/Batch functions
def insert_code(code: str, data: str, batchid: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a code into the database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO codes (code, data, redeemed, batchid) VALUES (?, ?, 0, ?)",
            (code, data, batchid)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Inserted code: {code}")
    except Exception as e:
        logger.error(f"Error inserting code: {e}")


def get_code(code: str, db_path: str = KILLFEED_DB_PATH):
    """Get a specific code."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT code, data, redeemed, user, batchid FROM codes WHERE code = ?", (code,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting code: {e}")
        return None


def redeem_code(code: str, user: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Redeem a code for a user."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE codes SET redeemed = 1, user = ? WHERE code = ?",
            (user, code)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Redeemed code {code} for {user}")
    except Exception as e:
        logger.error(f"Error redeeming code: {e}")


# Server functions
def insert_server(serverid: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a server into the database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO servers (serverid) VALUES (?)", (serverid,))
        conn.commit()
        conn.close()
        logger.debug(f"Inserted server: {serverid}")
    except Exception as e:
        logger.error(f"Error inserting server: {e}")


def get_servers(db_path: str = KILLFEED_DB_PATH):
    """Get all servers."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT serverid FROM servers")
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting servers: {e}")
        return []


# Device ban functions
def insert_device_ban(username: str, device_id: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a device ban into the database."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO deviceid_bans (username, device_id) VALUES (?, ?)",
            (username, device_id)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Inserted device ban: {device_id}")
    except Exception as e:
        logger.error(f"Error inserting device ban: {e}")


def is_device_id_banned(device_id: str, db_path: str = KILLFEED_DB_PATH) -> bool:
    """Check if a device ID is banned."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM deviceid_bans WHERE device_id = ?", (device_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Error checking device ban: {e}")
        return False


def get_all_banned_users(db_path: str = KILLFEED_DB_PATH):
    """Get all banned device IDs."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username, device_id FROM deviceid_bans")
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting banned users: {e}")
        return []


def unban_device_id(device_id: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Remove a device ID ban."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM deviceid_bans WHERE device_id = ?", (device_id,))
        conn.commit()
        conn.close()
        logger.debug(f"Removed device ban: {device_id}")
    except Exception as e:
        logger.error(f"Error removing device ban: {e}")

# it is not posting the kills in the channels, i have it in testing mode currently and it is not supposed to download a new logfile but it is supposed to still post everything in it instead of adding everything to see. this behavior may come from the recent database changes, additionally, i am noticing this does not support multiple sever settings as all server settings / logconfig is global


def unban_username(username: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Remove a device ID ban by username."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM deviceid_bans WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        logger.debug(f"Removed username ban: {username}")
    except Exception as e:
        logger.error(f"Error removing username ban: {e}")


def get_device_id_from_stats(username: str, db_path: str = KILLFEED_DB_PATH) -> Optional[str]:
    """Get device ID for a player (case-insensitive)."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT device_id FROM stats WHERE user = ? COLLATE NOCASE", (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting device ID: {e}")
        return None


def update_player_device_id(username: str, device_id: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Update a player's device ID in the stats table (case-insensitive lookup)."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE stats SET device_id = ? WHERE user = ? COLLATE NOCASE",
            (device_id, username)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Updated device ID for {username}: {device_id}")
    except Exception as e:
        logger.error(f"Error updating device ID for {username}: {e}")


def update_player_uid(username: str, uid: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Update a player's UID in the stats table (case-insensitive lookup)."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE stats SET uid = ? WHERE user = ? COLLATE NOCASE",
            (uid, username)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Updated UID for {username}: {uid}")
    except Exception as e:
        logger.error(f"Error updating UID for {username}: {e}")


def update_player_device_id_and_uid(username: str, device_id: str, uid: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Update a player's device ID and UID in the stats table (case-insensitive lookup)."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # Check if player exists first (case-insensitive)
        cursor.execute("SELECT user FROM stats WHERE user = ? COLLATE NOCASE", (username,))
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"Player {username} not found in stats table before update")
            conn.close()
            return
        
        cursor.execute(
            "UPDATE stats SET device_id = ?, uid = ? WHERE user = ? COLLATE NOCASE",
            (device_id, uid, username)
        )
        rows_affected = cursor.rowcount
        conn.commit()
        
        if rows_affected > 0:
            logger.info(f"Updated device ID and UID for {username} - Device: {device_id}, UID: {uid} ({rows_affected} row affected)")
        else:
            logger.warning(f"No rows updated for {username} - Device: {device_id}, UID: {uid}")
        
        # Verify the update (case-insensitive)
        cursor.execute("SELECT device_id, uid FROM stats WHERE user = ? COLLATE NOCASE", (username,))
        verify_result = cursor.fetchone()
        if verify_result:
            logger.debug(f"Verification - {username}: device_id={verify_result[0]}, uid={verify_result[1]}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error updating device ID and UID for {username}: {e}", exc_info=True)


def get_player_uid(username: str, db_path: str = KILLFEED_DB_PATH) -> Optional[str]:
    """Get UID for a player (case-insensitive)."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM stats WHERE user = ? COLLATE NOCASE", (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting UID: {e}")
        return None


def get_all_users_by_device_id(device_id: str, db_path: str = KILLFEED_DB_PATH):
    """Get all users with a specific device ID."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user FROM stats WHERE device_id = ?", (device_id,))
        result = cursor.fetchall()
        conn.close()
        return [row[0] for row in result] if result else []
    except Exception as e:
        logger.error(f"Error getting users by device ID: {e}")
        return []


# Config/Template functions
def insert_config(server_id: str, category: str, channelid: Optional[int] = None, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a config entry for a specific server."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO config (server_id, category, channelid) VALUES (?, ?, ?)",
            (server_id, category, channelid)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Inserted config: {server_id}:{category}")
    except Exception as e:
        logger.error(f"Error inserting config: {e}")


def get_config(server_id: str, category: str, db_path: str = KILLFEED_DB_PATH) -> Optional[int]:
    """Get a config value by server and category."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT channelid FROM config WHERE server_id = ? AND category = ?", (server_id, category))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return None


def update_config(server_id: str, category: str, channelid: int, db_path: str = KILLFEED_DB_PATH) -> None:
    """Update a config value for a specific server."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE config SET channelid = ? WHERE server_id = ? AND category = ?",
            (channelid, server_id, category)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Updated config: {server_id}:{category}")
    except Exception as e:
        logger.error(f"Error updating config: {e}")


def get_all_config(server_id: str, db_path: str = KILLFEED_DB_PATH):
    """Get all config entries for a specific server."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT category, channelid FROM config WHERE server_id = ?", (server_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting all config: {e}")
        return []


def get_all_config_dict(server_id: str, db_path: str = KILLFEED_DB_PATH):
    """Get all config entries for a specific server as a dictionary keyed by category."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT category, channelid FROM config WHERE server_id = ?", (server_id,))
        result = cursor.fetchall()
        conn.close()
        # Convert list of tuples to dictionary
        return {category: channelid for category, channelid in result}
    except Exception as e:
        logger.error(f"Error getting all config: {e}")
        return {}


# Server logs functions
def insert_server_log(server_id: str, log_type: str, log_data: str, db_path: str = KILLFEED_DB_PATH) -> None:
    """Insert a server log entry."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO server_logs (server_id, log_type, log_data) VALUES (?, ?, ?)",
            (server_id, log_type, log_data)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Inserted server log for {server_id}")
    except Exception as e:
        logger.error(f"Error inserting server log: {e}")


def get_server_logs(server_id: str, db_path: str = KILLFEED_DB_PATH):
    """Get logs for a specific server."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT log_type, log_data, created_at FROM server_logs WHERE server_id = ? ORDER BY created_at DESC",
            (server_id,)
        )
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error getting server logs: {e}")
        return []
