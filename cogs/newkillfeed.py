from discord.ext import commands, tasks
from config import Config
from os import path
from datetime import datetime
from utils.Weapons import Weapons as Weapons
from utils.closestLoc import getClosestLocation # Kept for now
import sys, os, time, math, sqlite3, re, discord, logging, asyncio, aiofiles, aiohttp, pytz
from utils.heatmap import generate_heatmap
region = sqlite3.connect("db/region.db")
rg = region.cursor()

deviceban = sqlite3.connect("db/deviceidban.db")
dbans = deviceban.cursor()

activitydata = sqlite3.connect("db/activitydata.db")
actdata = activitydata.cursor()

tables = [
    "CREATE TABLE IF NOT EXISTS data (activedata)",
    "CREATE TABLE IF NOT EXISTS onlinecount (activedata)",
    "CREATE TABLE IF NOT EXISTS killcount (activedata int)",
    "CREATE TABLE IF NOT EXISTS deathcount (activedata int)",
    "CREATE TABLE IF NOT EXISTS deathdata (activedata)",
    "CREATE TABLE IF NOT EXISTS killdata (activedata)"
]
for stmt in tables:
    actdata.execute(stmt)

r = actdata.execute("SELECT * FROM data").fetchall()
ro = actdata.execute("SELECT * FROM onlinecount").fetchall()
kills = actdata.execute("SELECT * FROM killcount").fetchall()
deaths = actdata.execute("SELECT * FROM deathcount").fetchall()
deathdata = actdata.execute("SELECT * FROM deathdata").fetchall()
killdata = actdata.execute("SELECT * FROM killdata").fetchall()

if not deathdata:
    print("Inserting into db")
    actdata.execute("INSERT INTO deathdata (activedata) VALUES ('0;0;0;0;0;0')")

if not killdata:
    print("Inserting into db")
    actdata.execute("INSERT INTO killdata (activedata) VALUES ('0;0;0;0;0;0')")

if not deaths:
    actdata.execute("INSERT INTO deathcount (activedata) VALUES (0)")

if not kills:
    actdata.execute("INSERT INTO killcount (activedata) VALUES (0)")

if not r:
    print("Inserting into db")
    actdata.execute("INSERT INTO data (activedata) VALUES ('0;0;0;0;0;0;0;0;0;0;0;0')")

if not ro:
    actdata.execute("INSERT INTO onlinecount (activedata) VALUES ('0;0;0;0;0;0')")
#actdata.execute("UPDATE data SET activedata = ?", ('0;0;0;0;0;0;0;0;0;0;0;0',)) # DEPRECIATED - Website required
#actdata.execute("UPDATE onlinecount SET activedata = ?", ('0;0;0;0;0;0',)) # DEPRECIATED - Website required

activitydata.commit()
activitydata.close()

stats = sqlite3.connect("db/stats.db")
st = stats.cursor()
bodypart = ''
class Killfeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weapons = Weapons.weapons
        self.reported = {}
        self.last_log = {}
        self.headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
        logging.basicConfig(level=logging.INFO)
        self.FirstTime = True
        self.server_iterator = 0
        self.testing = False
        self.last_updated_server = None

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Started bot")
        self.fetch_logs.start()

    @staticmethod
    async def new_logfile(fp) -> bool:
        async with aiofiles.open(fp, "r") as f:
            text = await f.read()
            logs = len(re.findall("AdminLog", text))
        return logs == 1

    async def process_active_servers(self):
        """
        Iterates over all known servers and processes their logs.
        """
        if self.testing:
            log_acquired = True
        tasks_to_run = []

        server_db = sqlite3.connect("db/servers.db")
        cursor = server_db.cursor()
        registered_servers = cursor.execute("SELECT * FROM servers").fetchall()

        if not registered_servers:
            print("No configured servers found. Initialize via setup commands.")
            return

        self.server_count = len(registered_servers)

        for entry in registered_servers:
            server_id = entry[0]
            print(f"[{server_id}] Processing server entry")

            server_db_path = f"db/{server_id}.db"
            if not os.path.exists(server_db_path):
                print(f"Missing DB for server {server_id}. Initialize it before use.")
                continue

            server_config = sqlite3.connect(server_db_path)
            config_cursor = server_config.cursor()
            try:
                channel_map = config_cursor.execute("SELECT * FROM config").fetchall()
            except sqlite3.OperationalError as e:
                print(f"Server DB ({server_id}) misconfigured:\n{e}")
                continue
            finally:
                server_config.close()

            for label, target in channel_map:
                if target is None:
                    print(f"[{server_id}] Channel '{label}' is not configured. Skipping.")

            if not self.testing:
                log_acquired = await self.fetch_server_log(server_id)

            if log_acquired:
                tasks_to_run.append(self.check_log(server_id, channel_map))

        await asyncio.gather(*tasks_to_run)

    @tasks.loop(minutes=5)
    async def fetch_logs(self):
        await self.process_active_servers()

    async def check_server_log(self, server_id: int, db_config):

        dayz = "https://dayz.ginfo.gg/livonia/#location=" # Automatic map detection needed. Will provide incorrect map location if map != livonia
        async def checkUserExists(player):
            st.execute(f"SELECT * FROM stats WHERE user = ?", (player,))
            r = st.fetchall()
            if r == [] or r == [()]:
                st.execute(f"INSERT INTO stats (user, kills, deaths, alivetime, killstreak, deathstreak, dcid, money, bounty, device_id, last_location, vouchers) VALUES (?, 0, 0, ?, 0, 0, 0, 0, 0, 0, ?, ?)", (player, int(time.mktime(datetime.now().timetuple())), None, None))
                #print(f"Initialized for {player}")
                stats.commit()

        async def timeFunc(timestamp): # Revision needed
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

        def calculate_distance(x1, z1, x2, z2):
            return math.sqrt((x1 - x2) ** 2 + (z1 - z2) ** 2)

        log_file_path = path.abspath(path.join(path.dirname(__file__), "..", "files", f"{server_id}.ADM"))
        logging.info(f"[{server_id}] Analyzing log file: {log_file_path}")

        channel_map = {
            "build": self.bot.get_channel(db_config[0][1]),
            "death": self.bot.get_channel(db_config[1][1]),
            "kill": self.bot.get_channel(db_config[2][1]),
            "hit": self.bot.get_channel(db_config[3][1]),
            "heatmap": self.bot.get_channel(db_config[4][1]),
            "flag": self.bot.get_channel(db_config[5][1]),
            "online": self.bot.get_channel(db_config[6][1]),
            "deathcount": self.bot.get_channel(db_config[7][1]),
            "killcount": self.bot.get_channel(db_config[8][1]),
            "ban_notify": self.bot.get_channel(db_config[9][1]),
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

        async with aiofiles.open(log_file_path, "r") as file:
            async for raw_line in file:
                line = raw_line.strip()

                match_player = re.search(r'Player "([^"]+)"', line)
                if match_player:
                    await checkUserExists(match_player.group(1))

                if line in line_tracker:
                    continue

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

                if channel_map["online"]:
                    online_match = re.search(r"(\d+)(?=\s*players)", line)
                    if online_match:
                        try:
                            player_total = int(online_match.group(1))
                            await channel_map["online"].edit(name=f"Online: {player_total}")
                            self.last_updated_server = server_id
                        except Exception:
                            pass

                if "AdminLog" in line and previous_log_marker != line:
                    if await self.new_logfile(log_file_path):
                        self.last_log[server_id] = line
                        self.reported[server_id] = []
                        line_tracker = self.reported[server_id]

                line_tracker.append(line)
                counter_activity += 1

                body_match = re.search(r'into ([^(]+)', line)
                current_bodypart = body_match.group(1) if body_match else ""

                if "(DEAD)" in line or "committed suicide" in line:
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    player_killed = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')

                    if "committed suicide" in line:
                        counter_deaths += 1
                        embed = discord.Embed(
                            title=f"Suicide | {timestamp}",
                            description=f"**{player_killed}** committed suicide",
                            color=0xE40000,
                        )
                        await channel_map["death"].send(embed=embed)

                    elif "hit by explosion" in line:
                        counter_deaths += 1
                        counter_kills += 1
                        explosion_type = re.search(r"\[HP: 0\] hit by explosion \((.*)\)", line).group(1)
                        embed = discord.Embed(
                            title=f"Exploded | {timestamp}",
                            description=f"**{player_killed}** died from explosion ({explosion_type})",
                            color=0xE40000,
                        )
                        await channel_map["kill"].send(embed=embed)

                elif "killed by Player" in line:
                    counter_deaths += 1
                    counter_kills += 1
                    print("PvP event detected")

                    try:
                        player_killer = re.search(r'killed by Player "(.*?)"', line).group(1)
                        player_killed = re.search(r'[\'"](.*?)[\'"]', line).group(1)
                        timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                        timestamp = await timeFunc(timestamp)

                        st.execute("UPDATE stats SET kills = kills + 1, killstreak = killstreak + 1, deathstreak = 0 WHERE user = ?", (player_killer,))
                        st.execute("UPDATE stats SET deaths = deaths + 1, killstreak = 0, deathstreak = deathstreak + 1, alivetime = ? WHERE user = ?",
                                   (int(time.mktime(datetime.now().timetuple())), player_killed))
                        stats.commit()

                        timealive_ts = st.execute("SELECT alivetime FROM stats WHERE user = ?", (player_killed,)).fetchone()[0]
                        timealive = datetime.now() - datetime.fromtimestamp(timealive_ts)
                        days = timealive.days
                        hours, remainder = divmod(timealive.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        seconds += timealive.microseconds / 1e6
                        timealivestr = ''
                        if days > 0: timealivestr += f'{days} Day{"s" if days > 1 else ""}, '
                        if hours > 0: timealivestr += f'{hours} Hour{"s" if hours > 1 else ""}, '
                        if minutes > 0: timealivestr += f'{minutes} Minute{"s" if minutes > 1 else ""}, '
                        if int(seconds) > 0: timealivestr += f'{int(seconds)} Second{"s" if int(seconds) > 1 else ""}'

                        # Update global stats
                        with sqlite3.connect("db/activitydata.db") as conn:
                            conn.execute("UPDATE killcount SET activedata = activedata + 1")
                            conn.commit()

                        killer_data = st.execute("""SELECT p1.*, (SELECT COUNT(*) FROM stats p2 WHERE p2.kills > p1.kills) as KillRank FROM stats p1 WHERE user = ?""", (player_killer,)).fetchall()
                        victim_data = st.execute("""SELECT p1.*, (SELECT COUNT(*) FROM stats p2 WHERE p2.kills > p1.kills) as KillRank FROM stats p1 WHERE user = ?""", (player_killed,)).fetchall()

                        coords = re.findall(r'pos=<([^>]+)>', line)
                        killer_coords = re.sub(r',\s*', ';', coords[0])
                        killer_coords = re.sub(r'\.\d+', '', killer_coords)
                        victim_coords = re.sub(r',\s*', ';', coords[1])
                        victim_coords = re.sub(r'\.\d+', '', victim_coords)

                        #location = getClosestLocation(victim_coords) # Removed until closest Loc revision

                        weapon = re.search(r" with (.*) from", line) or re.search(r"with (.*)", line)
                        weapon = weapon.group(1) if weapon else "Unknown"
                        for key in Weapons.weapons['data']:
                            if weapon == key:
                                weapon = Weapons.weapons['data'][weapon]

                        #templist = []
                        #weaponstr = ''
                        ##for i in emojis:
                        ##    clean_weapon = weapon.replace('-', '').replace(' ', '')
                        ##    if clean_weapon == i.name or clean_weapon == i.name[:-1]:
                        ##        emojiinstance = str(i)
                        ##        organized = emojiinstance.split(':')
                        ##        templist.append(organized)
                        #if templist:
                        #    weaponstr += '\n# '
                        #    templist = sorted(templist, key=lambda x: x[1][-1])
                        #    weaponstr += ''.join(':' + ':'.join(i) for i in templist)

                        try:
                            distance = round(float(re.search(r"from ([0-9.]+) meters", line).group(1)), 2)
                        except AttributeError:
                            distance = 0.0

                        embed = discord.Embed(
                            title=f"PvP Kill | {timestamp}",
                            description=f"""**{player_killer}** killed **{player_killed}**

                **Weapon**: `{weapon}` ({distance}m) {'hit' if current_bodypart else ''} {current_bodypart}
                **[Killer]({dayz + killer_coords}) - [Victim]({dayz + victim_coords})**
                **{player_killer}'s Stats**:
                K/D - {(round(killer_data[0][1]/killer_data[0][2], 2)) if float(killer_data[0][2]) > 0 else float(killer_data[0][1])} | {killer_data[0][2]} Death{'s' if float(killer_data[0][2]) > 1 else ''}  {killer_data[0][1]} Kill{'s' if float(killer_data[0][1]) > 1 else ''} | Ranked #{killer_data[0][10] if float(killer_data[0][10]) > 0 else '1'} Kills
                Killstreak - {killer_data[0][5]}
                **{player_killed}'s Stats:**
                K/D - {round(victim_data[0][1]/victim_data[0][2], 2) if victim_data[0][2] != 0 else victim_data[0][1]} | {victim_data[0][2]} Death{'s' if victim_data[0][2] > 1 else ''} {victim_data[0][1]} Kill{'s' if victim_data[0][1] > 1 else ''} | Ranked #{victim_data[0][10] if victim_data[0][10] > 0 else '1'} Deaths
                DeathStreak - {victim_data[0][4]}
                {'Time Alive - ' if int(int(seconds) + hours + minutes + days) > 0 else ''}{timealivestr}
                """,
                            color=0xE40000,
                        ).set_thumbnail(url=Config.EMBED_IMAGE).set_footer(text=Config.EMBED_FOOTER, icon_url=Config.EMBED_FOOTER_IMAGE)

                        await channel_map["kill"].send(embed=embed)

                    except Exception as e:
                        print(e)
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print(exc_type, fname, exc_tb.tb_lineno)
                        continue

                elif "bled out" in line:
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    victim = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')
                    embed = discord.Embed(
                        title=f"Bled Out | {timestamp}",
                        description=f"**{victim}** bled out",
                        color=0xE40000,
                    )
                    await channel_map["death"].send(embed=embed)

                elif any(wolf in line for wolf in ["Animal_CanisLupus_Grey", "Animal_CanisLupus_White"]):
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    victim = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')
                    counter_deaths += 1
                    embed = discord.Embed(
                        title=f"Wolf Kill | {timestamp}",
                        description=f"**{victim}** was killed by a Wolf",
                        color=0xE40000,
                    )
                    await channel_map["death"].send(embed=embed)

                elif any(bear in line for bear in ["Animal_UrsusArctos", "Brown Bear"]):
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    victim = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')
                    counter_deaths += 1
                    embed = discord.Embed(
                        title=f"Bear Kill | {timestamp}",
                        description=f"**{victim}** was killed by a Bear",
                        color=0xE40000,
                    )
                    await channel_map["death"].send(embed=embed)

                elif "hit by FallDamage" in line:
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    victim = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')
                    counter_deaths += 1
                    embed = discord.Embed(
                        title=f"Fall Death | {timestamp}",
                        description=f"**{victim}** fell to their death",
                        color=0xE40000,
                    )
                    await channel_map["death"].send(embed=embed)

                elif "died" in line:
                    timestamp = str(re.search(r"(\d+:\d+:\d+)", line).group(1))
                    timestamp = await timeFunc(timestamp)
                    victim = str(re.search(r'Player\s+"?(.*?)"?\s+\(.*?\)', line).group(1)).strip(' "\'')
                    counter_deaths += 1
                    embed = discord.Embed(
                        title=f"Died | {timestamp}",
                        description=f"**{victim}** died",
                        color=0xE40000,
                    )
                    await channel_map["death"].send(embed=embed)

                    #except Exception as e:
                    #    print(e)
                    #    continue
                logging.info(f"[{server_id}] Log review complete. Updating site-wide stats...")

    # Commit aggregate stats to activity database
        site_db = sqlite3.connect("db/activitydata.db")
        stats_cursor = site_db.cursor()
        stats_cursor.execute("UPDATE killcount SET activedata = activedata + ?", (counter_kills,))
        stats_cursor.execute("UPDATE deathcount SET activedata = activedata + ?", (counter_deaths,))
        site_db.commit()
        site_db.close()

        def update_series(table_name: str, value: int):
            conn = sqlite3.connect('db/activitydata.db')
            cursor = conn.cursor()
            current = cursor.execute(f"SELECT activedata FROM {table_name}").fetchone()[0]
            history = current.split(';')[1:]  # Skip first empty
            history.append(str(value))
            result = ';'.join([''] + history)
            cursor.execute(f"UPDATE {table_name} SET activedata = ?", (result,))
            conn.commit()
            conn.close()

        update_series('onlinecount', counter_online)
        update_series('killdata', counter_kills)
        update_series('deathdata', counter_deaths)
        update_series('data', counter_activity)

        # Update Discord channel stats
        try:
            activity_conn = sqlite3.connect('db/activitydata.db')
            cur = activity_conn.cursor()
            if channel_map["deathcount"]:
                total_deaths = cur.execute('SELECT activedata FROM deathcount').fetchone()[0]
                await channel_map["deathcount"].edit(name=f"Total Deaths: {total_deaths}")
            if channel_map["killcount"]:
                total_kills = cur.execute('SELECT activedata FROM killcount').fetchone()[0]
                await channel_map["killcount"].edit(name=f"Total Kills: {total_kills}")
            activity_conn.close()
        except Exception as e:
            print(f"Error while publishing to Discord: {e}")

        # Finalize per-server processing state
        self.server_iterator += 1
        if self.server_iterator >= self.server_count:
            self.FirstTime = False
            print("FirstTime flag reset after all servers processed.")

        # Generate heatmap
        unique_locations = list({coord for coord in player_coords})
        if channel_map["heatmap"]:
            generate_heatmap('./utils/y.jpg', unique_locations)
            heatmap_embed = discord.Embed(
                title="Player Location Heatmap",
                description=f"Entries: {len(unique_locations)}\n<t:{int(time.mktime(datetime.now().timetuple()))}:R>",
                color=0xE40000
            ).set_image(url="attachment://heatmap.jpg") # A better implementation is desired (Maybe stream data instead?)
            await channel_map["heatmap"].send(embed=heatmap_embed, file=discord.File("heatmap.jpg")) # A better implementation is desired (Maybe stream data instead?)

async def fetch_server_log(self, server_id):
    """
    Downloads the log file for a given Nitrado server.
    """
    logging.info(f"[{server_id}] Initiating log download")

    async with aiohttp.ClientSession() as session:
        try:
            # Optional: Fetch metadata
            metadata = await session.get(
                "https://api.nitrado.net/services", headers=self.headers
            )
            _ = await metadata.read()  # Discard or use later if needed

            server_info = await session.get(
                f"https://api.nitrado.net/services/{server_id}/gameservers",
                headers=self.headers
            )
            if server_info.status != 200:
                logging.warning(f"[{server_id}] Failed to fetch server info ({server_info.status})")
                return False

            details = await server_info.json()
            username = details["data"]["gameserver"]["username"]
            game_type = details["data"]["gameserver"]["game"].lower()

            if game_type == "dayzps":
                relative_path = "dayzps/config/DayZServer_PS4_x64.ADM"
            elif game_type == "dayzxb":
                relative_path = "dayzxb/config/DayZServer_X1_x64.ADM"
            else:
                logging.error(f"[{server_id}] Unsupported game type: {game_type}")
                return False

            download_endpoint = f"https://api.nitrado.net/services/{server_id}/gameservers/file_server/download?file=/games/{username}/noftp/{relative_path}"
            token_response = await session.get(download_endpoint, headers=self.headers)

            if token_response.status != 200:
                logging.error(f"[{server_id}] Failed to retrieve download token ({token_response.status})")
                return False

            token_data = await token_response.json()
            download_url = token_data["data"]["token"]["url"]

            file_response = await session.get(download_url, headers=self.headers)
            if file_response.status != 200:
                logging.error(f"[{server_id}] Log file download failed ({file_response.status})")
                return False

            local_fp = path.abspath(path.join(path.dirname(__file__), "..", "files", f"{server_id}.ADM"))
            async with aiofiles.open(local_fp, mode="wb+") as f:
                await f.write(await file_response.read())

            logging.info(f"[{server_id}] Log download complete")
            return True

        except Exception as e:
            logging.exception(f"[{server_id}] Exception during log fetch: {e}")
            return False


async def setup(bot):
    await bot.add_cog(Killfeed(bot))
