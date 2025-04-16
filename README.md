# 🎮 Console DayZ Multipurpose Bot

A feature-rich Discord bot designed for DayZ server management with deep Nitrado integration. Includes log tracking, PvP stats, player interaction alerts, full stats tracking, and heatmap visualization.

---

## 🎯 Features

### ✅ Real-Time Log Tracking
- Continuously polls DayZ ADM logs to track PvP kills, suicides, fall deaths, explosions, animal attacks, etc.
- Sends clean, embed-rich updates to individual log channels.

### 🧾 Rich PvP Logs & Stats
- Displays kills with full details: weapon, distance, location, and embedded kill/death statistics.
- Tracks K/D ratio, streaks, time alive, and player rank.

### 📈 Heatmap Generation
- Automatically or manually generate heatmaps showing player hotspots.
- Use `/generateallheatmap` to output an image per-server.

~~### 🔐 Device ID Ban Management~~ *(To be implemented)*
- Commands like `/bandevice` and `/unbandevice` are prepared for future admin-level banning by device ID.

### 🛠️ Custom Logging Channels
- Assign different logs to specific channels using `/logconfig`.
- Logs supported: deaths, kills, suicides, hits, flag interactions, fall deaths, etc.

### 🗺️ Region & Flag Tracking
- Create flag zones using `/addarea`.
- Automatically detect and log flag raising/lowering in critical map zones.

### 💾 Redeemable Code System
- Use `/generatekeys` to create codes for rewards or roles.
- Users redeem via `/redeem`, and all redemptions are logged for audit.

### 🔗 Player Linking & Stats
- Players link their in-game name via `/link`.
- Use `/stats` or `/stats [username]` to show personal or public stats.

---

## 🔧 Admin Commands

- `/link` – Connect Discord user to a character name
- `/stats [user]` – Pulls stats: K/D, time alive, streaks, etc.
- `/nitradoserver` – Add/remove Nitrado server by ID
- `/logconfig` – Assign log output categories to Discord channels
- `/addkit` `/modifykit` – Create and edit predefined loot kits
- `/generatekeys` – Generate codes in bulk
- `/redeem` – Players use this to claim codes
- `/sync` – Resync slash commands (if required)

Classic prefix command available for sync:
```
<PREFIX>sync
```
---

## 🧠 Setup Guide
1. Clone the repo.
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

### 1. ⚙️ `config.py` Configuration

Edit `config.py` and fill in these fields:

```python
class Config:
    NITRADO_TOKEN = ""      # Your Nitrado API token
    DISCORD_TOKEN = ""      # Your Discord bot token
    BOT_PREFIX = "."        # Prefix for non-slash fallback commands
    EMBED_IMAGE = ""        # Optional thumbnail for embeds
    EMBED_FOOTER = "Your Server Name"  # Displayed at bottom of all embeds
    EMBED_FOOTER_IMAGE = "" # Footer icon URL
    EMBED_COLOR = ''        # Hex color for embeds, e.g., 0xE40000
```

Make sure all tokens are valid and quotes are used properly.

---

### 2. 🐍 Install Dependencies

Use the provided `requirements.txt` to install everything:

```bash
pip install -r requirements.txt
```

---

### 3. 🚀 Run the Bot

```bash
python bot.py
```

---

### 4. 🔌 First-Time Initialization

After the bot is online:

#### ➕ Add Your Server
Use:
```
/nitradoserver
```
- Input your Nitrado server ID
- Choose action: `Add`
- The bot will then create a database entry for the configuration of your server.

  Note: You can always run the command /serverlist to view your Nitrado servers, and their associated ID to get the correct ID needed

#### 🔧 Configure Logging Channels
Use:
```
/logconfig
```
- Assign log types (`death`, `kill`, `hit`, `flag`, `onlinecount`, etc.) to Discord channels.
- Each log type will automatically route messages to the configured location, or behave accordingly

---

## 📁 Database Overview

| File | Purpose |
|------|---------|
| `stats.db`        | Player stats (kills, deaths, streaks, time) |
| `region.db`       | Flag detection zones |
| `servers.db`      | Tracks registered servers |
| `deviceidban.db`  | Future support for banning players |
| `codes.db`        | Redeemable key storage |
| `activitydata.db` | Heatmap, kill/death tracking |



# Important Message Below!

## 🔐 Security Warning

**Important:** Make sure your bot is set to **private** in the Discord Developer Portal.

If your bot is public (`bot_public == True`), it may be exploited by unauthorized users to access admin-level commands. The bot includes a safety check:

```python
async def on_ready():
    print("Bot Ready")
    s = await bot.application_info()
    if s.bot_public == True:
        print("""
              
              ERROR: SECURITY WARNING
Bot is public, this is a security risk as commands are only restricted to members who have admin access.
If unauthorized persons add the bot to their server, they may gain access to sensitive admin commands.
Set the bot to **private** in the Discord Developer Portal under "Bot Settings".
If you need help, contact b0nggo.

Application closing automatically.
              """)
        exit()
```
