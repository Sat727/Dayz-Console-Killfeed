# Console DayZ Multipurpose Bot

A feature-rich Discord bot designed for DayZ server management with deep Nitrado integration.  
Includes log tracking, PvP stats, player interaction alerts, full stats tracking, heatmap visualization, and automatic alt account detection with device-based banning.

---

## Features

### Real-Time Log Tracking
- Continuously polls DayZ ADM logs to track PvP kills, suicides, fall deaths, explosions, animal attacks, and connection events.
- Sends detailed embed messages to configured log channels.
- Automatically tracks player connection/disconnection events.

### Rich PvP Logs and Statistics
- Displays kills with full details: weapon, distance, location, and embedded kill/death statistics.
- Tracks K/D ratio, kill/death streaks, time alive, and player rank.
- Maintains persistent player statistics across wipes and sessions.

### Automatic Alt Account Detection
- Tracks device IDs and UIDs from DayZ server authentication logs (RPT format).
- Automatically identifies when multiple accounts use the same device.
- Sends alerts to designated staff channels for both banned and non-banned alt accounts.
- Prevents duplicate processing of the same authentication events.

### Device-Based Ban Management
- Ban or unban entire devices across all configured servers via Nitrado API.
- Automatic ban enforcement when banned devices attempt to connect.
- Separate alerts for banned devices vs. regular alt accounts.
- Staff-only query commands to investigate suspected ban evaders.

### Heatmap Generation
- Automatically or manually generate heatmaps showing player hotspots.
- Use `/generateallheatmap` to output an image per server.

### Custom Logging Channels
- Assign different log types to specific channels using `/logconfig`.
- Supports: deaths, kills, suicides, hits, flag interactions, connections, disconnections, alt alerts, and banned device alerts.

### Region and Flag Tracking
- Create flag zones using `/addarea`.
- Automatically detect and log flag raising/lowering in critical map zones.

### Redeemable Code System
- Use `/generatekeys` to create codes for rewards or roles.
- Users redeem via `/redeem`, and all redemptions are logged for audit.

### Player Linking and Statistics
- Players link their in-game name via `/link`.
- Use `/stats` or `/stats [username]` to show personal or public statistics.

---

## Admin Commands

### Server Management
- `/nitradoserver` - Add or remove Nitrado servers by ID
- `/serverlist` - View all configured Nitrado servers and their IDs
- `/logconfig` - Assign log output categories to Discord channels

### Player Statistics and Linking
- `/link [username]` - Connect Discord user to a character name
- `/stats [username]` - View player statistics (K/D, time alive, streaks, ranks)
- `/unlink` - Remove Discord account linking
- `/staffunlink [user]` - Force unlink a player account (admin only)

### Device Ban Management
- `/bandevice [device_id or username]` - Ban a device across all servers (auto-bans all associated accounts on Nitrado)
- `/unbandevice [device_id or username]` - Unban a device across all servers
- `/querydevice [username]` - Staff command to view a player's device ID and all linked accounts
- `/queryalts [device_id]` - Staff command to find all accounts on a specific device
- `/viewbans` - View all banned devices and their associated usernames

### Content Management
- `/generatekeys [amount]` - Generate redeemable codes in bulk
- `/redeem` - Players use this to claim codes
- `/addarea [x] [z] [radius] [channel] [name]` - Create flag detection zones
- `/removearea` - Remove flag detection zones

### Bot Management
- `/sync` - Resync slash commands (if required)
- `/resetdatabase [database_name]` - Reset specified database

Classic prefix command available for sync:
```
<PREFIX>sync
```

---

## Device Ban System and Alt Detection

### How It Works

The bot automatically tracks device IDs and UIDs from DayZ server authentication logs:

1. **Authentication Event Monitoring**: When a player connects to the server, the DayZ server logs authentication events in the RPT file containing device ID and UID information.
2. **Device Tracking**: The bot parses these logs and stores the device ID associated with each player account.
3. **Alt Detection**: If multiple accounts share the same device ID, they are flagged as potential alt accounts.
4. **Ban Detection**: If a device is marked as banned in the database, any player attempting to connect with that device is automatically banned on the server.

### Logging and Alerts

Configure alert channels using `/logconfig`:

- **AltAlert**: Receives notifications when non-banned alt accounts are detected. Displays all accounts on the shared device.
- **AltBanned**: Receives notifications when a banned device is detected. The account is automatically banned on the server, and all associated alt accounts are listed.

### Using Device Bans

1. **Ban a Device**:
   ```
   /bandevice username:PlayerName
   ```
   Or if you have the device ID:
   ```
   /bandevice device_id:VUZwoETj2mkhZSZuUxOg5T8jwr0TrB4R_pt4klUoRio=
   ```
   This bans all current and future accounts on that device across all configured servers.

2. **Investigate a Player**:
   ```
   /querydevice username:SuspectedPlayer
   ```
   This shows:
   - The player's device ID
   - All other accounts on that device
   - Ban status of the device

3. **Check a Device**:
   ```
   /queryalts device_id:VUZwoETj2mkhZSZuUxOg5T8jwr0TrB4R_pt4klUoRio=
   ```
   Lists all accounts ever associated with that device.

4. **Unban a Device**:
   ```
   /unbandevice device_id:VUZwoETj2mkhZSZuUxOg5T8jwr0TrB4R_pt4klUoRio=
   ```
   This removes the ban, allowing accounts on that device to connect again.

### Automatic Enforcement

Once a device is banned:
- Any player attempting to connect with that device is automatically banned on the Nitrado server.
- An alert is sent to the AltBanned channel.
- The player cannot bypass the ban by using a different account on the same device.

---

## Python 3.10 Installation (Windows)

Before running the bot, you will need Python 3.10 (not 3.11 or later).

### 1. Download Python 3.10
- Visit: https://www.python.org/downloads/release/python-3100/
- Scroll down and download the Windows installer (64-bit).

### 2. Run the Installer
When the installer opens:
- IMPORTANT: Check the box labeled "Add Python 3.10 to PATH" at the bottom of the first window.
- Click "Install Now."

### 3. Verify Installation
After installation, open a terminal and run:
```bash
python --version
```
You should see:
```
Python 3.10.x
```

If you get an error, restart your computer and try again.

### 4. Upgrade pip (Optional but Recommended)
```bash
python -m pip install --upgrade pip
```

---

## Setup Guide

1. Clone the repository:
   ```bash
   git clone https://github.com/Sat727/Dayz-Console-Killfeed.git
   cd Dayz-Console-Killfeed
   ```

2. Edit `config.py` with your Nitrado token, Discord bot token, and channel mappings.

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

---

## Configuration

### config.py

Edit `config.py` and fill in these fields:

```python
class Config:
    NITRADO_TOKEN = ""              # Your Nitrado API token
    DISCORD_TOKEN = ""              # Your Discord bot token
    BOT_PREFIX = "."                # Prefix for non-slash fallback commands
    EMBED_IMAGE = ""                # Optional thumbnail for embeds
    EMBED_FOOTER = "Your Server Name"  # Displayed at bottom of all embeds
    EMBED_FOOTER_IMAGE = ""         # Footer icon URL
    EMBED_COLOR = ''                # Hex color for embeds, e.g., 0xE40000
```

Make sure all tokens are valid and quotes are used properly.

### Installing Dependencies

Use the provided `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Running the Bot

```bash
python main.py
```

### First-Time Initialization

After the bot is online:

1. Add Your Server:
   ```
   /nitradoserver
   ```
   Input your Nitrado server ID and select "Add". The bot will create a database entry for your server configuration.

   You can run `/serverlist` anytime to view all your Nitrado servers and their IDs.

2. Configure Logging Channels:
   ```
   /logconfig
   ```
   Select the server you added in step 1, then assign log types (death, kill, hit, flag, onlinecount, altalert, altbanned, etc.) to Discord channels.

---

## Database Overview

| File | Purpose |
|------|----------|
| `killfeed.db` | Player statistics (kills, deaths, streaks, time alive, device IDs, UIDs, linked Discord accounts), flag detection zones, server configurations, banned devices, redeemable codes, heatmap data, and activity tracking |

### Device ID Storage

Device IDs are stored as base64-encoded SHA256 hashes of the DayZ client device identifier. UIDs are stored as 40-character hexadecimal strings representing the Steam UID equivalent on DayZ client.

Both fields are automatically populated when players authenticate to the server. No manual entry is required by administrators.

---

## Security Warning

IMPORTANT: Ensure your bot is set to PRIVATE in the Discord Developer Portal.

If your bot is public, unauthorized users may be able to add it to their servers and access admin-level commands. The bot includes a built-in safety check and will exit if this condition is detected at startup.

To set the bot to private:
1. Go to the Discord Developer Portal (https://discord.com/developers/applications)
2. Select your bot application
3. Navigate to "Bot Settings"
4. Find the "Public Bot" toggle and disable it
