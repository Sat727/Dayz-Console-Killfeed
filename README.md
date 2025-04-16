# Console DayZ Multipurpose Bot

A feature-rich Discord bot designed for DayZ server management with deep Nitrado integration. Includes log tracking, PvP stats, player interaction alerts, automated device ID banning, and full support for heatmaps and flag area monitoring.

## 🎯 Features

### ✅ Real-Time Log Tracking
- Continuously polls DayZ server logs (ADM) and parses for PvP kills, deaths, suicides, fall damage, animal attacks, explosions, and more.
- Broadcasts deaths and events to specific Discord channels per-server via config.

### 🧾 Rich PvP Logs & Stats
- Detects who killed who, weapon used, hit location, distance, and displays a full stats breakdown for both killer and victim.
- Tracks killstreaks, deathstreaks, K/D ratios, time alive, and global rank.

### 📈 Heatmap Generation
- Automatically or manually generate heatmaps of player locations to visualize activity zones on your map.
- `/generateallheatmap` command can be used per server.

~~### Device ID Ban Management
- Admin commands to ban or unban players by their device ID (`/bandevice`, `/unbandevice`).
- Device bans persist via SQLite and can be managed from Discord.~~ *(To be implemented)*

### 🛠️ Customizable Logging Channels
- Per-category logging (Builds, Deaths, Hits, Interactions, etc).
- Configure with `/logconfig`.

### 🗺️ Area Monitoring
- Track flag interactions in defined regions via `/addarea`.
- Automatically detects when players raise flags in sensitive zones and notifies a configured channel.

### 💾 Code System for Rewards
- Secure, batched key generation and redemption for roles, perks, or other integrations.
- Audit logs included for tracking generated/redeemed codes.

### 🔗 Account Linking
- Players can link their in-game names to Discord accounts via `/link` to retrieve stats via `/stats`.

## 🔧 Admin Commands (Slash & Prefixed)

Some core commands:
- `/link` – Link Discord account to in-game player.
- `/stats [username]` – Show personal or specified player stats.
- `/addkit` / `/modifykit` – Manage donation or admin kits.
- `/nitradoserver` – Register or remove a Nitrado server for tracking.
- `/logconfig` – Assign Discord channels to specific log types.
- `/bandevice` / `/unbandevice` – Ban or unban users via device ID.
- `/generatekeys` / `/redeem` – Generate and redeem user codes.

You can also sync commands with the classic `<PREFIX>sync` (if you’ve got the proper permissions).

## 📁 Database Structure

The bot uses several SQLite databases:
- `stats.db` – Kills, deaths, streaks, time alive, linked Discord IDs
- `region.db` – Flag event regions (Used for events)
- `servers.db` – Registered Nitrado server IDs
- `deviceidban.db` – Banned device IDs
- `codes.db` – Generated keys and redemption logs

## 🧩 Requirements

- Python 3.9+
- `discord.py` with app command support
- `aiohttp`, `aiofiles`, `matplotlib`, `PIL`, `sqlite3`

You can install all dependencies using:
```bash
pip install -r requirements.txt
```

## ⚙️ Setup

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
