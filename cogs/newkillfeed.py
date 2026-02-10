from discord.ext import commands, tasks
from config import Config
from os import path
from datetime import datetime
from utils.Weapons import Weapons as Weapons
from utils.closestLoc import getClosestLocation
from utils.heatmap import generate_heatmap
from utils import killfeed_helpers, killfeed_database, killfeed_events, killfeed_nitrado
import sys, os, time, sqlite3, re, discord, logging, asyncio, aiofiles
import aiohttp

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database connections
killfeed_database.initialize_master_db()
conn, st = killfeed_database.initialize_stats_db()
killfeed_database.initialize_activity_db()
stats = conn
class Killfeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weapons = Weapons.weapons
        self.reported = {}
        self.last_log = {}
        self.server_maps = {}  # Store map info per server
        self.headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
        self.FirstTime = True
        self.server_iterator = 0
        self.testing = False
        self.last_updated_server = None
        self.task_started = False  # Flag to prevent duplicate task starts

    async def safe_edit_channel(self, channel, **kwargs):
        try:
            #await channel.edit(**kwargs)
            pass
        except asyncio.TimeoutError:
            logger.warning(f"Timeout editing channel {getattr(channel, 'id', None)}")
        except Exception as e:
            logger.exception(f"Error editing channel {getattr(channel, 'id', None)}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Started bot")
        # Only start the task once to prevent duplicate runs
        if not self.task_started and not self.fetch_logs.is_running():
            self.fetch_logs.start()
            self.task_started = True

    async def process_active_servers(self):
        """
        Iterates over all known servers and processes their logs.
        """
        if self.testing:
            log_acquired = True
        tasks_to_run = []

        # Use consolidated database
        registered_servers = killfeed_database.get_servers()

        if not registered_servers:
            print("No configured servers found. Initialize via setup commands.")
            return

        self.server_count = len(registered_servers)

        for entry in registered_servers:
            server_id = entry[0]
            logger.debug(f"[{server_id}] Processing server entry")

            # Get config from consolidated database for this specific server
            try:
                channel_map = killfeed_database.get_all_config_dict(str(server_id))
            except Exception as e:
                logger.error(f"Server config ({server_id}) misconfigured:\n{e}")
                continue

            if not self.testing:
                log_acquired = await killfeed_nitrado.fetch_server_log(server_id, self.server_maps)
            else:
                log_acquired = True

            if log_acquired:
                server_map = self.server_maps.get(server_id, "chernarus").lower()
                tasks_to_run.append(self.check_server_log(server_id, channel_map, server_map))

        await asyncio.gather(*tasks_to_run)

    @tasks.loop(minutes=5)
    async def fetch_logs(self):
        try:
            await self.process_active_servers()
        except Exception as e:
            logger.error(f"Error in fetch_logs task: {e}", exc_info=True)

    @fetch_logs.before_loop
    async def before_fetch_logs(self):
        """Wait for bot to be ready before starting the task loop."""
        await self.bot.wait_until_ready()
        logger.info("Fetch logs task started - running every 5 minutes")

    async def check_server_log(self, server_id: int, db_config, server_map: str = "chernarus"):

        # Get map URL and location capability
        dayz = killfeed_nitrado.get_map_url(server_map)
        can_use_locations = killfeed_nitrado.can_use_locations(server_map)

        log_file_path = path.abspath(path.join(path.dirname(__file__), "..", "files", f"{server_id}.ADM"))
        logger.info(f"[{server_id}] Analyzing log file: {log_file_path}")

        # Check if log file exists before processing
        if not os.path.exists(log_file_path):
            logger.warning(f"[{server_id}] Log file not found at {log_file_path}. Skipping this server.")
            return

        # Build channel map from config dictionary - safely handle None values
        channel_map = {
            "build": self.bot.get_channel(db_config.get("Build")) if db_config.get("Build") else None,
            "death": self.bot.get_channel(db_config.get("Death")) if db_config.get("Death") else None,
            "kill": self.bot.get_channel(db_config.get("Kill")) if db_config.get("Kill") else None,
            "hit": self.bot.get_channel(db_config.get("Hit")) if db_config.get("Hit") else None,
            "heatmap": self.bot.get_channel(db_config.get("Heatmap")) if db_config.get("Heatmap") else None,
            "flag": self.bot.get_channel(db_config.get("BaseInteraction")) if db_config.get("BaseInteraction") else None,
            "online": self.bot.get_channel(db_config.get("OnlineCount")) if db_config.get("OnlineCount") else None,
            "deathcount": self.bot.get_channel(db_config.get("DeathCount")) if db_config.get("DeathCount") else None,
            "killcount": self.bot.get_channel(db_config.get("KillCount")) if db_config.get("KillCount") else None,
            "ban_notify": self.bot.get_channel(db_config.get("BanNotification")) if db_config.get("BanNotification") else None,
            "connect": self.bot.get_channel(db_config.get("Connect")) if db_config.get("Connect") else None,
            "disconnect": self.bot.get_channel(db_config.get("Disconnect")) if db_config.get("Disconnect") else None,
        }

        if server_id not in self.reported:
            self.reported[server_id] = []
        if server_id not in self.last_log:
            self.last_log[server_id] = ""

        line_tracker = self.reported[server_id]
        previous_log_marker = self.last_log[server_id]

        player_coords = []
        current_bodypart = ""
        counter_online = 0
        counter_kills = 0
        counter_deaths = 0
        counter_activity = 0
        reading_players = False
        online_count_updated = False

        async with aiofiles.open(log_file_path, "r") as file:
            async for raw_line in file:
                line = raw_line.strip()

                # Check if player exists in database
                match_player = re.search(r'Player "([^"]+)"', line)
                if match_player:
                    killfeed_database.check_user_exists(st, match_player.group(1), stats)

                # Skip already reported lines
                if line in line_tracker:
                    continue

                # Handle player list parsing
                if "##### PlayerList log:" in line:
                    reading_players = True
                    player_coords.clear()
                    counter_online = 0
                elif re.match(r"\d{2}:\d{2}:\d{2} \| #####", line):
                    reading_players = False
                elif reading_players:
                    coord_match = re.search(r'pos=<([\d.]+), [\d.]+, ([\d.]+)>', line)
                    if coord_match:
                        x, z = map(float, coord_match.groups())
                        player_coords.append((x, z))
                        counter_online += 1

                # Update online player count if channel exists (only once per check to avoid rate limits)
                if channel_map["online"] and not online_count_updated:
                    online_match = re.search(r"(\d+)(?=\s*players)", line)
                    if online_match:
                        try:
                            player_total = int(online_match.group(1))
                            ch = channel_map.get("online")
                            if ch:
                                await self.safe_edit_channel(ch, name=f"Online: {player_total}")
                            self.last_updated_server = server_id
                            online_count_updated = True
                        except Exception as e:
                            logger.error(f"Error updating online count: {e}")

                # Check for new log file
                if "AdminLog" in line and previous_log_marker != line:
                    if await killfeed_helpers.new_logfile(log_file_path):
                        self.last_log[server_id] = line
                        self.reported[server_id] = []
                        line_tracker = self.reported[server_id]

                line_tracker.append(line)
                counter_activity += 1

                # Extract body part hit
                current_bodypart = killfeed_helpers.extract_bodypart(line)

                # Handle different event types
                try:
                    # Check connection/disconnection events first (no "(DEAD)" check)
                    if killfeed_events.is_player_connected_event(line):
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        player = killfeed_helpers.extract_player_name(line)
                        if player:
                            # Initialize player stats on connect
                            killfeed_database.check_user_exists(st, player, stats)
                            embed = await killfeed_events.create_player_connected_embed(player, timestamp_str)
                            if channel_map.get("connect"):
                                await channel_map["connect"].send(embed=embed)

                    elif killfeed_events.is_player_disconnected_event(line):
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        player = killfeed_helpers.extract_player_name(line)
                        if player:
                            embed = await killfeed_events.create_player_disconnected_embed(player, timestamp_str)
                            if channel_map.get("disconnect"):
                                await channel_map["disconnect"].send(embed=embed)

                    # Check specific death types BEFORE generic "(DEAD)" check
                    elif killfeed_events.is_suicide_event(line):
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        player_killed = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if player_killed:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, player_killed, conn_death)
                            killfeed_database.update_death_stats(cursor_death, player_killed, conn_death)
                            conn_death.close()
                            logger.info(f"Suicide death recorded: {player_killed}")
                        
                        embed = await killfeed_events.create_suicide_embed(player_killed, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                    elif killfeed_events.is_explosion_event(line):
                        counter_deaths += 1
                        counter_kills += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        player_killed = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if player_killed:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, player_killed, conn_death)
                            killfeed_database.update_death_stats(cursor_death, player_killed, conn_death)
                            conn_death.close()
                            logger.info(f"Explosion death recorded: {player_killed}")
                        
                        explosion_type = killfeed_events.extract_explosion_type(line)
                        embed = await killfeed_events.create_explosion_embed(player_killed, explosion_type, timestamp_str)
                        if channel_map["kill"]:
                            await channel_map["kill"].send(embed=embed)

                    elif killfeed_events.is_bleed_out_event(line):
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        victim = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if victim:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, victim, conn_death)
                            killfeed_database.update_death_stats(cursor_death, victim, conn_death)
                            conn_death.close()
                            logger.info(f"Bleed out death recorded: {victim}")
                        
                        embed = await killfeed_events.create_bleed_out_embed(victim, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                    elif killfeed_events.is_wolf_kill_event(line):
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        victim = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if victim:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, victim, conn_death)
                            killfeed_database.update_death_stats(cursor_death, victim, conn_death)
                            conn_death.close()
                            logger.info(f"Wolf kill death recorded: {victim}")
                        
                        embed = await killfeed_events.create_wolf_kill_embed(victim, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                    elif killfeed_events.is_bear_kill_event(line):
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        victim = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if victim:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, victim, conn_death)
                            killfeed_database.update_death_stats(cursor_death, victim, conn_death)
                            conn_death.close()
                            logger.info(f"Bear kill death recorded: {victim}")
                        
                        embed = await killfeed_events.create_bear_kill_embed(victim, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                    elif killfeed_events.is_fall_death_event(line):
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        victim = killfeed_helpers.extract_player_name(line)
                        
                        # Update death stats
                        if victim:
                            conn_death = killfeed_database.get_connection()
                            cursor_death = conn_death.cursor()
                            killfeed_database.check_user_exists(cursor_death, victim, conn_death)
                            killfeed_database.update_death_stats(cursor_death, victim, conn_death)
                            conn_death.close()
                            logger.info(f"Fall death recorded: {victim}")
                        
                        embed = await killfeed_events.create_fall_death_embed(victim, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                    # Check PvP kills
                    elif killfeed_events.is_pvp_kill_event(line):
                        counter_deaths += 1
                        counter_kills += 1
                        logger.info("PvP event detected")

                        try:
                            player_killer, player_killed = killfeed_helpers.extract_killer_victim(line)
                            logger.debug(f"Extracted - Killer: '{player_killer}', Victim: '{player_killed}'")
                            
                            if not player_killer or not player_killed:
                                logger.warning(f"Failed to extract killer/victim from: {line}")
                                continue
                            
                            timestamp = killfeed_helpers.extract_timestamp(line)
                            timestamp_str = await killfeed_helpers.time_func(timestamp)

                            # Ensure both players exist and update stats with fresh connection
                            conn_ensure = killfeed_database.get_connection()
                            cursor_ensure = conn_ensure.cursor()
                            killfeed_database.check_user_exists(cursor_ensure, player_killer, conn_ensure)
                            killfeed_database.check_user_exists(cursor_ensure, player_killed, conn_ensure)
                            conn_ensure.close()
                            
                            # Update stats using fresh connection
                            conn_stats = killfeed_database.get_connection()
                            cursor_stats = conn_stats.cursor()
                            killfeed_database.update_kill_stats(cursor_stats, player_killer, player_killed, conn_stats)
                            conn_stats.close()
                            logger.info(f"Stats updated: {player_killer} killed {player_killed}")

                            # Calculate time alive
                            conn_temp = killfeed_database.get_connection()
                            cursor_temp = conn_temp.cursor()
                            cursor_temp.execute("SELECT alivetime FROM stats WHERE user = ?", (player_killed,))
                            result = cursor_temp.fetchone()
                            conn_temp.close()
                            timealive_ts = result[0] if result else int(time.time())
                            timealive = datetime.now() - datetime.fromtimestamp(timealive_ts)
                            days = timealive.days
                            hours, remainder = divmod(timealive.seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            seconds += timealive.microseconds / 1e6
                            timealivestr = killfeed_helpers.format_time_alive(int(seconds), minutes, hours, days)

                            # Update global stats (using consolidated database)
                            killfeed_database.increment_activity_counters(kills=1, deaths=0)

                            # Get player stats
                            killer_stats = killfeed_database.get_player_stats(st, player_killer)
                            victim_stats = killfeed_database.get_player_stats(st, player_killed)

                            # Extract coordinates
                            coords = killfeed_helpers.extract_coordinates_from_line(line)
                            killer_coords = killfeed_helpers.format_coordinates(coords[0]) if coords else ""
                            victim_coords = killfeed_helpers.format_coordinates(coords[1]) if len(coords) > 1 else ""

                            # Get location if available
                            location = ""
                            if can_use_locations:
                                location = getClosestLocation(victim_coords) if victim_coords else ""

                            # Extract weapon
                            weapon = killfeed_helpers.extract_weapon(line, Weapons.weapons)

                            # Extract distance
                            distance = killfeed_helpers.extract_distance(line)

                            # Create embed
                            embed = await killfeed_events.create_pvp_kill_embed(
                                player_killer, player_killed, weapon, distance, current_bodypart,
                                timestamp_str, killer_stats, victim_stats, timealivestr, dayz
                            )
                            
                            # Add coordinate links if available
                            if killer_coords and victim_coords:
                                embed.description = embed.description.replace(
                                    "**[Killer]" ,
                                    f"**[Killer]({dayz + killer_coords}) - [Victim]({dayz + victim_coords})**"
                                )

                            if channel_map["kill"]:
                                await channel_map["kill"].send(embed=embed)

                        except Exception as e:
                            logger.error(f"Error processing PvP kill: {e}")
                            logger.exception(e)

                    # Generic death as last resort
                    elif killfeed_events.is_death_event(line) and "died" in line:
                        counter_deaths += 1
                        timestamp = killfeed_helpers.extract_timestamp(line)
                        timestamp_str = await killfeed_helpers.time_func(timestamp)
                        victim = killfeed_helpers.extract_player_name(line)
                        embed = await killfeed_events.create_generic_death_embed(victim, timestamp_str)
                        if channel_map["death"]:
                            await channel_map["death"].send(embed=embed)

                except Exception as e:
                    logger.error(f"Error processing log line: {e}")
                    continue

        # Commit aggregate stats to activity database
        logger.info(f"[{server_id}] Log review complete. Activity - Kills: {counter_kills}, Deaths: {counter_deaths}")
        killfeed_database.increment_activity_counters(counter_kills, counter_deaths)

        # Update activity series
        killfeed_database.update_series('onlinecount', counter_online)
        killfeed_database.update_series('killdata', counter_kills)
        killfeed_database.update_series('deathdata', counter_deaths)
        killfeed_database.update_series('data', counter_activity)

        # Update Discord channel stats (only if there was new activity)
        if counter_kills > 0 or counter_deaths > 0:
            try:
                total_deaths = killfeed_database.get_total_deaths()
                total_kills = killfeed_database.get_total_kills()
                
                if channel_map["deathcount"]:
                    try:
                        #await channel_map["deathcount"].edit(name=f"Total Deaths: {total_deaths}")
                        pass
                    except Exception as e:
                        logger.debug(f"Could not update deathcount channel: {e}")
                if channel_map["killcount"]:
                    try:
                        #await channel_map["killcount"].edit(name=f"Total Kills: {total_kills}")
                        pass
                    except Exception as e:
                        logger.debug(f"Could not update killcount channel: {e}")
                    
                logger.info(f"[{server_id}] Updated kill/death counters")
            except asyncio.TimeoutError:
                logger.warning(f"[{server_id}] Discord API timeout when updating channels")
            except Exception as e:
                logger.error(f"[{server_id}] Error updating Discord channels: {e}")

        # Finalize per-server processing state
        self.server_iterator += 1
        if self.server_iterator >= self.server_count:
            self.FirstTime = False
            print("FirstTime flag reset after all servers processed.")

        # Generate heatmap (only for Chernarus and only if there's new location data)
        unique_locations = list({coord for coord in player_coords})
        if channel_map["heatmap"] and server_map == "chernarus" and len(unique_locations) > 0 and counter_activity > 0:
            try:
                generate_heatmap('./utils/y.jpg', unique_locations)
                heatmap_embed = discord.Embed(
                    title="Player Location Heatmap",
                    description=f"Entries: {len(unique_locations)}\n<t:{int(time.mktime(datetime.now().timetuple()))}:R>",
                    color=0xE40000
                ).set_image(url="attachment://heatmap.jpg")
                if channel_map["heatmap"]:
                    await channel_map["heatmap"].send(embed=heatmap_embed, file=discord.File("heatmap.jpg"))
                logger.info(f"[{server_id}] Heatmap sent with {len(unique_locations)} location entries")
            except asyncio.TimeoutError:
                logger.warning(f"[{server_id}] Discord API timeout when sending heatmap")
            except Exception as e:
                logger.error(f"[{server_id}] Error generating heatmap: {e}")



async def setup(bot):
    await bot.add_cog(Killfeed(bot))
