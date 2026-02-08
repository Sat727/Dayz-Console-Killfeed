import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from typing import List
from os import kill, path
import aiohttp, aiofiles, asyncio, os, string, re, json, datetime, random
from config import Config
from utils.heatmap import generate_heatmap
from utils.nitradoFuncs import NitradoFunctions
import logging
import typing
from typing import Union

#try:
#    class KitSelectionMenu(discord.ui.Select):
#        options = []
#        with open('utils/kits.json', 'r') as kitf:
#            data = json.load(kitf)
#            for i, kit in enumerate(data['kits']):
#                options.append(discord.SelectOption(label=f"{i+1}. {data['kits'][kit]}"))
#except Exception as e:
#    print(e)
#    class KitSelectionMenu():
#        options = None

Nitrado = NitradoFunctions()
region = sqlite3.connect("db/region.db")
rg = region.cursor()
rg.execute("CREATE TABLE IF NOT EXISTS region (x, z, radius, channelid, name)")
region.commit()

database=sqlite3.connect('db/codes.db')
c = database.cursor()
c.execute("CREATE TABLE IF NOT EXISTS codes (code, data, redeemed, user, batchid)")
database.commit()

stats = sqlite3.connect("db/stats.db")
st = stats.cursor()
st.execute("CREATE TABLE IF NOT EXISTS stats (user, kills int, deaths int, alivetime, deathstreak int, killstreak int, dcid, money, bounty, device_id)") # Money, Bounty values for possible implemention of economy
stats.commit()


servers = sqlite3.connect("db/servers.db")
s = servers.cursor()
s.execute("CREATE TABLE IF NOT EXISTS servers (serverid)")
servers.commit()

deviceban = sqlite3.connect("db/deviceidban.db")
dbans = deviceban.cursor()
dbans.execute('''CREATE TABLE IF NOT EXISTS deviceid_bans (
                        username TEXT, 
                        device_id TEXT)''')
deviceban.commit()


def is_device_id_banned(device_id):
    dbans.execute("SELECT 1 FROM deviceid_bans WHERE device_id = ?", (device_id,))
    result = dbans.fetchone()
    return result is not None

def get_device_id_from_stats(username):
    st.execute("SELECT device_id FROM stats WHERE user = ?", (username,))
    result = st.fetchone()
    return result[0] if result else None

def get_all_banned_users():
    conn = sqlite3.connect("db/deviceidban.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, device_id FROM deviceid_bans")
    result = cursor.fetchall()
    conn.close()
    return result

def unban_device_id(device_id):
    conn = sqlite3.connect("db/deviceidban.db")
    dbans = conn.cursor()

    # Delete all rows with the device_id
    dbans.execute("DELETE FROM deviceid_bans WHERE device_id = ?", (device_id,))
    conn.commit()

    conn.close()
    

categories = ("Build", "Death", "Kill", "Hit", "Heatmap", "BaseInteraction", "OnlineCount", 'DeathCount', 'KillCount', "BanNotification")

def updateDatabase(categories=categories):
    template = sqlite3.connect("db/template.db")
    tem = template.cursor()
    tem.execute("CREATE TABLE IF NOT EXISTS config (category, channelid)")
    ins = [i for i in categories if i not in [i[0] for i in tem.execute("SELECT * FROM config").fetchall()]]
    try:
        tem.execute("SELECT * FROM config")
        tem.execute("CREATE TABLE IF NOT EXISTS config (category, channelid)")
        for i in ins:
            tem.execute("INSERT or IGNORE INTO config (category, channelid) VALUES (?,NULL)", (i,))
            template.commit()
        print("Created template database")
    except Exception as e:
        print(e)
        print("Database template may have already been created. Skipping creation, and adding new setting if any")
        for i in categories:
            tem.execute("INSERT or IGNORE INTO config (category, channelid) VALUES (?,NULL)", (i,))
            template.commit()
    print("Updating database")
    f = []
    for (dirpath, dirnames, filenames) in os.walk('db'):
        print(filenames)
        f.append(filenames)
    print(f)
    print("Getting settings")
    if len(f) > 1:
        print('Printing list')
        print(f)
        f = ([i[:-3] for i in f[0] if i[:-3].isdigit()])
    else:
        print("Printing List")
        print(f)
        f = ([i[:-3] for i in f[0] if i.isdigit()])
    print(f'Attempting to update {len(f)} databases.')
    
    print(f)
    for fp in f:
        entries = 0
        main = sqlite3.connect(f"db/{fp}.db")
        m = main.cursor()
        ins = [i for i in categories if i not in [i[0] for i in m.execute("SELECT * FROM config").fetchall()]]
        for l in ins:
            m.execute("INSERT INTO 'config' (category, channelid) VALUES (?,NULL)", (l,))
            entries = entries + 1
        main.commit()
        if len(m.execute("SELECT * FROM config").fetchall()) > len(categories):
            print("The length of the end database larger than template. Popping rows...")
            pop = len(m.execute("SELECT * FROM config").fetchall())
            top = len(categories)
            while pop >= top:
                if pop == top:
                    break
                m.execute(f"DELETE FROM config WHERE rowid={pop}")
                pop -= 1
        main.commit()
        print(f"Merged {entries} records from template into {fp}")

updateDatabase()

#async def NitradoServerCheck(NitradoID):
#    pass
#
#class Kits():
#    pass


class ServerSelect(discord.ui.Select):
    """Select menu for choosing a server from the database"""
    def __init__(self, user_id: int, callback_func, action_type: str = "general"):
        self.user_id = user_id
        self.callback_func = callback_func
        self.action_type = action_type
        
        # Get servers from database
        s.execute("SELECT * FROM servers")
        servers_list = s.fetchall()
        
        options = []
        for server in servers_list:
            server_id = str(server[0])
            options.append(discord.SelectOption(label=f"Server {server_id}", value=server_id))
        
        if not options:
            options.append(discord.SelectOption(label="No servers configured", value="none"))
        
        super().__init__(
            placeholder="Choose a server...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Only allow the user who invoked the command
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You are not permitted to do this.", ephemeral=True)
            return
        
        if self.values[0] == "none":
            await interaction.response.send_message("No servers are configured. Use `/nitradoserver` to add one.", ephemeral=True)
            return
        
        await self.callback_func(interaction, int(self.values[0]))


class ServerSelectView(discord.ui.View):
    """View containing the server select menu"""
    def __init__(self, user_id: int, callback_func, action_type: str = "general"):
        super().__init__()
        self.add_item(ServerSelect(user_id, callback_func, action_type))


class ChannelSelect(discord.ui.Select):
    """Select menu for choosing a channel for log output"""
    def __init__(self, user_id: int, server_id: int, callback_func):
        self.user_id = user_id
        self.server_id = server_id
        self.callback_func = callback_func
        
        # Get available categories
        options = [
            discord.SelectOption(label=cat, value=cat) 
            for cat in categories
        ]
        
        super().__init__(
            placeholder="Choose a log category...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Only allow the user who invoked the command
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You are not allowed to interact with this menu.", ephemeral=True)
            return
        
        await self.callback_func(interaction, self.server_id, self.values[0])


class ChannelSelectView(discord.ui.View):
    """View containing the channel select menu"""
    def __init__(self, user_id: int, server_id: int, callback_func):
        super().__init__()
        self.add_item(ChannelSelect(user_id, server_id, callback_func))


class Commands(commands.Cog):





    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logging.basicConfig(level=logging.INFO)
        self.categories = categories
        #self.synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        print("Commands Ready")
        
        #await self.tree.sync()
        #print("Synced")

    @app_commands.checks.has_permissions(administrator=True)
    @commands.command()
    async def sync(self, ctx) -> None:
        fmt = await ctx.bot.tree.sync()
        await ctx.send(f"Synced {len(fmt)}")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="addarea", description="Set a location to be listened to by flag event")
    async def addarea(self, interaction:discord.Interaction, x_coord:float, z_coord:float, radius:int, channel:discord.TextChannel, name:str):
        rg.execute("SELECT * FROM region")
        rows = rg.fetchall()
        if len(rows) > 25:
            await interaction.response.send_message("You have more than 25 events. The limit is 25")
        else:
            rg.execute("INSERT INTO region (x, z, radius, channelid, name) VALUES (?, ?, ?, ?, ?)", (x_coord, z_coord, radius, channel.id, name))
            region.commit()
            await interaction.response.send_message(f"Listening to flags at {x_coord} {z_coord} and posting to {channel}")
            await interaction.guild.id


    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="auditlog", description="Send audit log file")
    async def auditlog(self, interaction:discord.Interaction):
        await interaction.response.send_message(file=discord.File(r'./logs/audit.txt'))

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="addkit", description="Adds a kit to the kits file")
    async def addkit(self, interaction:discord.Interaction, kit_name:str):
        data = json.load('utils/kits.json')
        if kit_name in data.keys():
            await interaction.response.send_message("This kit already exists!")
            return
        data['kits'][kit_name] = []
        json.dump(data, 'utils/kits.json')
        await interaction.response.send_message(f"Added {kit_name} to the kit list!, use /modifykit to add items to the kit")
    
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="modifykit", description="Modifies existing kit")
    async def modifykit(self, interaction:discord.Interaction, kit_name:str):
        with open('utils/kits.json' 'r') as file:
            data = json.load('utils/kits.json')
            if data['kits']:
                if kit_name in data['kits']:
                    # Create a view that you can repeatedly add more, and more items to the kit
                    pass
            else:
                await interaction.response.send_message("There are no kits initialized into the kit file, please use /addkit")


        

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="terminatelastbatch", description="Deletes most recent generated keys")
    async def terminatelastbatch(self, interaction:discord.Interaction):
        if len(self.lastbatch) > 0:
            count = 0
            for i in self.lastbatch:
                c.execute("DELETE FROM codes WHERE code = ?", (i,))
                count += 1
            await interaction.response.send_message(f"Deleted {count} entries")
            self.lastbatch = []
            database.commit()
        else:
            await interaction.response.send_message("Last batch not detected/already deleted")

    #@app_commands.checks.has_permissions(administrator=True)
    #@app_commands.command(name="givekit", description="Give a donator kit to a specific user")
    #async def givekit(self, user:discord.Member, kit):
    #    pass

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="bandevice", description="Bans the target Device ID")
    async def bandevice(self, interaction: discord.Interaction, device_id: str = None, username: str = None):
        if device_id:
            if is_device_id_banned(device_id):
                await interaction.response.send_message(f"Device ID {device_id} is already banned.")
            else:
                conn = sqlite3.connect("db/deviceidban.db")
                dbans = conn.cursor()
                dbans.execute("INSERT INTO deviceid_bans (username, device_id) VALUES (?, ?)", ("Unknown", device_id))
                conn.commit()
                conn.close()
                await interaction.response.send_message(f"Successfully banned Device ID {device_id}.")
        elif username:
            device_id = get_device_id_from_stats(username)
            if device_id:
                if is_device_id_banned(device_id):
                    await interaction.response.send_message(f"Device ID {device_id} associated with {username} is already banned.")
                else:
                    conn = sqlite3.connect("db/deviceidban.db")
                    dbans = conn.cursor()
                    dbans.execute("INSERT INTO deviceid_bans (username, device_id) VALUES (?, ?)", (username, device_id))
                    conn.commit()
                    conn.close()
                    await interaction.response.send_message(f"Successfully banned {username} (Device ID {device_id}).")
            else:
                await interaction.response.send_message(f"No device ID associated with {username}. Please provide the device ID manually.")
        else:
            await interaction.response.send_message("Please provide either a device ID or a username.")


    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="unbandevice", description="Unbans the target Device ID")
    async def unbandevice(self, interaction: discord.Interaction, device_id: str = None, username: str = None):
        if not device_id and not username:
            await interaction.response.send_message("Please provide either a device ID or a username to unban.")
            return

        if device_id:
            if not is_device_id_banned(device_id):
                await interaction.response.send_message(f"Device ID {device_id} is not banned.")
            else:
                unban_device_id(device_id)
                await interaction.response.send_message(f"Successfully unbanned Device ID {device_id} and removed all associated usernames.")

        # Unban using username
        elif username:
            device_id = get_device_id_from_stats(username)
            if device_id:
                if not is_device_id_banned(device_id):
                    await interaction.response.send_message(f"Device ID {device_id} associated with {username} is not banned.")
                else:
                    unban_device_id(device_id)
                    await interaction.response.send_message(f"Successfully unbanned Device ID {device_id} and removed all associated usernames of {username}.")
            else:
                await interaction.response.send_message(f"No device ID associated with {username}.")

# Create a command to show all banned users with pagination
    @app_commands.command(name="viewbans", description="View all banned users and their device IDs.")
    async def viewbans(self, interaction: discord.Interaction):
        banned_users = get_all_banned_users()
    
        page_size = 5
        total_pages = (len(banned_users) // page_size) + (1 if len(banned_users) % page_size > 0 else 0)
    
        def create_embed(page_number):
            start = (page_number - 1) * page_size
            end = start + page_size
            page_data = banned_users[start:end]
    
            embed = discord.Embed(title="Banned Users", description="Showing banned users and their device IDs", color=0xE40000)
    
            description = ""
            for username, device_id in page_data:
                description += f"**Username**: {username} | **Device ID**: {device_id}\n\n\n"
    
            embed.description = description
            embed.set_footer(text=f"Page {page_number}/{total_pages}")
            return embed
    
        page_number = 1
        embed = create_embed(page_number)
        
        # Send the initial message and store it in message
        await interaction.response.send_message(embed=embed)

        message = await interaction.original_response()
    
        # Ensure message is not None
        if message:
            print("Message Found")
            await message.add_reaction("⬅️")
            await message.add_reaction("➡️")
        else:
            print("Message not found!")
            return
    
        def check(reaction, user):
            print("Checking response")
            return user == interaction.user and str(reaction.emoji) in ["⬅️", "➡️"]

        while True:
            try:
                print("Waiting for reaction")
                reaction, user = await interaction.client.wait_for("reaction_add", timeout=60.0, check=check)
                print("Response detected")
                if str(reaction.emoji) == "⬅️" and page_number > 1:
                    page_number -= 1
                elif str(reaction.emoji) == "➡️" and page_number < total_pages:
                    page_number += 1

                embed = create_embed(page_number)
                await message.edit(embed=embed)

                # Remove the reaction
                await message.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                await message.clear_reactions()
                break

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="terminatebatch", description="Deletes most recent generated keys")
    async def terminatebatch(self, interaction:discord.Interaction, batchid:int):
        c.execute("DELETE FROM codes WHERE batchid = ?", (batchid,))
        await interaction.response.send_message(f"Terminated {c.rowcount} codes from the database")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(value=[
        app_commands.Choice(name="Priority", value='priority'),
        ])
    @app_commands.command(name="generatekeys", description="Generate keys for users to redeem")
    async def generatekeys(self, interaction:discord.Interaction, amount:int, value:app_commands.Choice[str]):
        if amount > 136:
            await interaction.response.send_message("You cannot request more than 136 codes at a time")
        views = discord.ui.View()
        yes_button = discord.ui.Button(label="Yes", style=discord.ButtonStyle.green, custom_id='0')
        views.add_item(yes_button)
        no_button = discord.ui.Button(label="No", style=discord.ButtonStyle.red, custom_id='1')
        batch = []
        async def selection(choice):
            if choice.user == interaction.user:
                if choice.data.get('custom_id') == "0":
                    codes = []
                    raw_string = f''
                    try:
                        memory_db = [code[0] for code in c.execute("SELECT code FROM codes")]
                        batchid = len(memory_db) + 1
                        with open('logs/audit.txt', 'a') as log:
                            log.write(f'{interaction.user} ({interaction.user.id}) Generated {amount} {value.value} Keys in {interaction.channel.name} ({interaction.channel.id}) at {datetime.datetime.now().strftime("%m/%d/%Y, %I:%M %p")}\n')
                        def generate_key():
                            generated = random.choices(population=list(str(string.ascii_uppercase) + str(string.digits)), k=25)
                            if generated not in memory_db:
                                codes.append(generated)
                                memory_db.append(generated)
                            else:
                                generate_key()
                        for i in range(0,amount):
                            generate_key()
                        for co in codes:
                            raw_code = ''.join(l + '-' * (n % 5 == 4) for n, l in enumerate(co))[:-1]
                            batch.append(raw_code)
                            raw_string = raw_string + raw_code
                            c.execute("INSERT INTO codes (code, data, redeemed, batchid) VALUES (?,?,?,?)", (raw_code, value.value, 1, batchid))
                            raw_string += '\n'
                        self.lastbatch = batch
                        database.commit()
                        embed = discord.Embed(title=f"Generated {amount} {value.name} Keys", description=f'```\n{raw_string+"```"}', color=0xE40000()).set_footer(text=f'Batch ID: {batchid}')
                        await choice.response.send_message(embed=embed)
                        await choice.message.delete()
                    except Exception as e:
                        print(e)
                elif choice.data.get('custom_id') == "1":
                    await choice.response.send_message("Aborted key generation", ephemeral=True)
                    await choice.message.delete()
            else:
                print("Unauthorized button use")
                await choice.response.send_message("You do not have permission to select this!",ephemeral=True)
        no_button.callback = selection
        yes_button.callback = selection
        views.add_item(no_button)
        await interaction.response.send_message(f'Are you sure you want to generate {amount} {value.value} keys?',view=views)


    @app_commands.command(name="redeem", description="Redeem keys")
    async def redeem(self, interaction:discord.Interaction):
        class Redeem(discord.ui.Modal, title='Key Redemption'):
            username = discord.ui.TextInput(label='Username', required=True, style=discord.TextStyle.short, max_length=16, min_length=3)
            code = discord.ui.TextInput(label='Code', required=True, max_length=29, min_length=29, style=discord.TextStyle.long)
            async def on_submit(self, interaction: discord.Interaction):
                query = c.execute("SELECT * FROM codes WHERE code=?", (str(self.code),)).fetchall()
                if len(query) == 1:
                    if query[0][2] == 1:
                        if re.compile(r'[a-zA-Z0-9-_]*$').match(str(self.username)):
                            rows = c.execute("SELECT code FROM codes WHERE code = ?", (str(self.code),)).fetchall()
                            print(rows)
                            if len(rows) > 0:
                                print("Test")
                                try:
                                    with open('logs/audit.txt', 'a') as log:
                                        log.write(f'{interaction.user} ({interaction.user.id}) Redeemed code in {interaction.channel.name} ({interaction.channel.id}) for username {self.username} at {datetime.datetime.now().strftime("%m/%d/%Y, %I:%M %p")}\n')
                                        print("Passed x1")
                                except Exception as e:
                                    print(e)
                                data = str(await Nitrado.Priority(id=16655698, username=self.username, priority='Add'))
                                print(data)
                                if data.startswith("Successful"):
                                    c.execute("UPDATE codes SET redeemed = ?, user = ? WHERE code = ?", (0,str(self.username), str(self.code)))
                                    database.commit()
                                    await interaction.response.send_message(f"Redeemed {query[0][1]} for {self.username} on PS4")
                                else:
                                    await interaction.response.send_message(data)
                        else:
                            await interaction.response.send_message("Invalid username. Please try again!")
                    elif query[0][2] == 0:
                        await interaction.response.send_message("Code already redeemed!")
                else:
                    await interaction.response.send_message("Invalid code!")
        await interaction.response.send_modal(Redeem())
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="removearea", description="Remove a flag listener")
    async def removearea(self, interaction:discord.Interaction):
        rg.execute("SELECT * FROM region")
        rows = rg.fetchall()
        select = discord.ui.Select()
        select.placeholder = "Which area would you like to remove?"
        c = 0
        if rows == []:
            await interaction.response.send_message("No areas to remove. Create one using /addarea")
            return
        for i in rows:
            c+=1
            select.add_option(label=f"{i[-1]}",description=f"X:{i[0]}, {i[1]}",value=c)
        select.max_values = 1
        view = discord.ui.View()
        view.add_item(select)
        async def callback(interaction:discord.Interaction):
            rg.execute(f"DELETE FROM region WHERE name = ?", (i[-1],))
            region.commit()
            await interaction.response.send_message(f"Deleted {i[-1]} from your listeners")
            view.stop()
        select.callback = callback
        r = await interaction.response.send_message(view=view)
        view.wait()
        await r.delete()

    #@app_commands.checks.has_permissions(administrator=True)
    #@app_commands.command(name="staffgive", description="Give someone money for currency")
    #async def staffgive(self, interaction:discord.Interaction, amount : int):
    #    pass

    #@app_commands.checks.has_permissions(administrator=True)
    #@app_commands.command(name="staffremove", description="Remove someone's money for currency")
    #async def staffremove(self, interaction:discord.Interaction, amount : int):
    #    pass

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="Add someone"),
        app_commands.Choice(name="Remove", value="Remove someone"),
        ])
    @app_commands.command(name="banlist", description="Banlist Options")
    async def banlist(self, interaction:discord.Interaction, username:str, action:app_commands.Choice[str]):
        """Banlist management with server selection dropdown"""
        s.execute("SELECT * FROM servers")
        servers_list = s.fetchall()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.", ephemeral=True)
            return
        
        async def banlist_callback(cb_interaction: discord.Interaction, server_id: int):
            await cb_interaction.response.defer()
            data = await Nitrado.banPlayer(id=server_id, username=username, ban=action)
            # Convert bytes to string if necessary
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            # Ensure data is not empty
            message = data if data else "Ban action completed."
            await cb_interaction.followup.send(message)
        
        class BanListServerSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                    for server in servers_list
                ]
                super().__init__(
                    placeholder="Choose a server...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, sel_interaction: discord.Interaction):
                if sel_interaction.user.id != interaction.user.id:
                    await sel_interaction.response.send_message("You are not permitted to do this.", ephemeral=True)
                    return
                
                await banlist_callback(sel_interaction, int(self.values[0]))
        
        class BanListServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(BanListServerSelect())
        
        await interaction.response.send_message(
            f"Select a server to manage banlist for **{username}** (Action: {action.name}):",
            view=BanListServerView(),
            ephemeral=True
        )

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="Add someone"),
        app_commands.Choice(name="Remove", value="Remove someone"),
        ])
    @app_commands.command(name="priority", description="Priority Options")
    async def priority(self, interaction:discord.Interaction, username:str, action:app_commands.Choice[str]):
        """Priority management with server selection dropdown"""
        s.execute("SELECT * FROM servers")
        servers_list = s.fetchall()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.", ephemeral=True)
            return
        
        async def priority_callback(cb_interaction: discord.Interaction, server_id: int):
            await cb_interaction.response.defer()
            data = await Nitrado.Priority(id=server_id, username=username, priority=action)
            # Convert bytes to string if necessary
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            # Ensure data is not empty
            message = data if data else "Priority action completed."
            await cb_interaction.followup.send(message)
        
        class PriorityServerSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                    for server in servers_list
                ]
                super().__init__(
                    placeholder="Choose a server...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, sel_interaction: discord.Interaction):
                if sel_interaction.user.id != interaction.user.id:
                    await sel_interaction.response.send_message("You are not permitted to do this.", ephemeral=True)
                    return
                
                await priority_callback(sel_interaction, int(self.values[0]))
        
        class PriorityServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(PriorityServerSelect())
        
        await interaction.response.send_message(
            f"Select a server to manage priority for **{username}** (Action: {action.name}):",
            view=PriorityServerView(),
            ephemeral=True
        )

    #@app_commands.checks.has_permissions(administrator=True)
    #@app_commands.choices(action=[
    #    app_commands.Choice(name="Add", value="Add someone"),
    #    app_commands.Choice(name="Remove", value="Remove someone"),
    #    ])
#@app_commands.command(name="whitelist", description="Whitelist Options")
#async def whitelist(self, interaction:discord.Interaction, username:str, action:app_commands.Choice[str], server_id:int):
#    data = await Nitrado.getSettings(server_id)
#    data = json.loads(data)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="logconfig", description="Change the output of logs")
    async def logconfig(self, interaction:discord.Interaction):
        """Interactive log configuration using dropdown menus"""
        s.execute("SELECT * FROM servers")
        servers_list = s.fetchall()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.", ephemeral=True)
            return
        
        async def select_category_callback(ctx_interaction: discord.Interaction, server_id: int, category: str):
            """Callback for when user selects a category"""
            # Create a channel select view
            async def select_channel_callback(final_interaction: discord.Interaction, channel: discord.TextChannel | discord.VoiceChannel):
                """Callback for when user selects a channel"""
                logchannels = sqlite3.connect(f"db/{server_id}.db")
                lc = logchannels.cursor()
                lc.execute("UPDATE config SET channelid = ? WHERE category = ?", (channel.id, category))
                logchannels.commit()
                logchannels.close()
                await final_interaction.response.send_message(
                    f"Updated server `{server_id}` to send `{category}` logs to {channel.mention}",
                    ephemeral=True
                )
            
            # Create custom view with channels
            class ChannelView(discord.ui.View):
                def __init__(self):
                    super().__init__()
                    self.select_channel = discord.ui.ChannelSelect(
                        channel_types=[discord.ChannelType.text, discord.ChannelType.voice],
                        min_values=1,
                        max_values=1,
                        placeholder="Select a channel...",
                    )
                    self.select_channel.callback = self.channel_callback
                    self.add_item(self.select_channel)
                
                async def channel_callback(self, ch_interaction: discord.Interaction):
                    if ch_interaction.user.id != interaction.user.id:
                        await ch_interaction.response.send_message("You are not allowed to interact with this menu.", ephemeral=True)
                        return
                    await select_channel_callback(ch_interaction, self.select_channel.values[0])
            
            await ctx_interaction.response.send_message(
                f"Select a channel for `{category}` logs:",
                view=ChannelView(),
                ephemeral=True
            )
        
        # Create server select view
        class ServerSelectForLogConfig(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                    for server in servers_list
                ]
                super().__init__(
                    placeholder="Choose a server...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, sel_interaction: discord.Interaction):
                if sel_interaction.user.id != interaction.user.id:
                    await sel_interaction.response.send_message("You are not allowed to interact with this menu.", ephemeral=True)
                    return
                
                server_id = int(self.values[0])
                
                # Create category select view
                class CategorySelect(discord.ui.Select):
                    def __init__(self):
                        options = [
                            discord.SelectOption(label=cat, value=cat)
                            for cat in categories
                        ]
                        super().__init__(
                            placeholder="Choose a log category...",
                            min_values=1,
                            max_values=1,
                            options=options
                        )
                    
                    async def callback(self, cat_interaction: discord.Interaction):
                        if cat_interaction.user.id != interaction.user.id:
                            await cat_interaction.response.send_message("You are not allowed to interact with this menu.", ephemeral=True)
                            return
                        
                        await select_category_callback(cat_interaction, server_id, self.values[0])
                
                class CategorySelectView(discord.ui.View):
                    def __init__(self):
                        super().__init__()
                        self.add_item(CategorySelect())
                
                await sel_interaction.response.send_message(
                    f"Select a log category for server `{server_id}`:",
                    view=CategorySelectView(),
                    ephemeral=True
                )
        
        class ServerSelectViewForLogConfig(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(ServerSelectForLogConfig())
        
        await interaction.response.send_message(
            "Select a server to configure:",
            view=ServerSelectViewForLogConfig(),
            ephemeral=True
        )


    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="Add a Nitrado server to the bot"),
        app_commands.Choice(name="Remove", value="Remove a Nitrado server from the bot"),
        ])
    @app_commands.command(name="nitradoserver", description="Change nitrado servers associated with the bot")
    async def nitrado(self, interaction:discord.Interaction, action:app_commands.Choice[str]):
        if action.name == "Add":
            # For adding, use a modal for the server ID
            class AddServerModal(discord.ui.Modal, title="Add Nitrado Server"):
                server_id = discord.ui.TextInput(label="Nitrado Server ID", placeholder="Enter the numeric server ID")
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    if modal_interaction.user.id != interaction.user.id:
                        await modal_interaction.response.send_message("You are not allowed to submit this form.", ephemeral=True)
                        return
                    
                    try:
                        nitradoserver = int(self.server_id.value)
                    except ValueError:
                        await modal_interaction.response.send_message("Server ID must be a number.", ephemeral=True)
                        return
                    
                    s.execute("SELECT * FROM servers")
                    r = s.fetchall()
                    
                    try:
                        if nitradoserver not in [i[0] for i in r]:
                            logchannels = sqlite3.connect(f"db/{nitradoserver}.db")
                            lc = logchannels.cursor()
                            lc.execute("CREATE TABLE IF NOT EXISTS config (category, channelid)")
                            for i in self.categories:
                                lc.execute("INSERT INTO config (category, channelid) VALUES (?,NULL)", (i,))
                            logchannels.commit()
                            logchannels.close()
                            s.execute("INSERT INTO servers (serverid) VALUES (?)", (nitradoserver,))
                            servers.commit()
                            await modal_interaction.response.send_message(f"Initialized server `{nitradoserver}`\nUse `/logconfig` to configure the server.", ephemeral=True)
                        else:
                            await modal_interaction.response.send_message("This nitrado server already exists in the database.", ephemeral=True)
                    except Exception as e:
                        logchannels = sqlite3.connect(f"db/{nitradoserver}.db")
                        lc = logchannels.cursor()
                        lc.execute("CREATE TABLE IF NOT EXISTS config (category, channelid)")
                        for i in self.categories:
                            lc.execute("INSERT INTO config (category, channelid) VALUES (?, 0)", (i,))
                        logchannels.commit()
                        logchannels.close()
                        s.execute("INSERT INTO servers (serverid) VALUES (?)", (nitradoserver,))
                        servers.commit()
                        await modal_interaction.response.send_message(f"Initialized server `{nitradoserver}`\nUse `/logconfig` to configure the server.", ephemeral=True)
            
            await interaction.response.send_modal(AddServerModal())
        
        elif action.name == "Remove":
            # For removing, use a dropdown
            s.execute("SELECT * FROM servers")
            servers_list = s.fetchall()
            
            if not servers_list:
                await interaction.response.send_message("No servers in the database to remove.", ephemeral=True)
                return
            
            class RemoveServerSelect(discord.ui.Select):
                def __init__(self):
                    options = [
                        discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                        for server in servers_list
                    ]
                    super().__init__(
                        placeholder="Choose a server to remove...",
                        min_values=1,
                        max_values=1,
                        options=options
                    )
                
                async def callback(self, sel_interaction: discord.Interaction):
                    if sel_interaction.user.id != interaction.user.id:
                        await sel_interaction.response.send_message("You are not allowed to interact with this menu.", ephemeral=True)
                        return
                    
                    server_id = int(self.values[0])
                    
                    try:
                        os.remove(f"db/{server_id}.db")
                        s.execute(f"DELETE FROM servers WHERE serverid = ?", (server_id,))
                        servers.commit()
                        await sel_interaction.response.send_message(f"Removed server `{server_id}` from the database.", ephemeral=True)
                    except Exception as e:
                        await sel_interaction.response.send_message(f"Error removing server: {str(e)}", ephemeral=True)
            
            class RemoveServerView(discord.ui.View):
                def __init__(self):
                    super().__init__()
                    self.add_item(RemoveServerSelect())
            
            await interaction.response.send_message(
                "Select a server to remove:",
                view=RemoveServerView(),
                ephemeral=True
            )





    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="serverlist", description="Check servers list associated with your nitrado Token")
    async def servers(self, interaction:discord.Interaction):
       headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
       async with aiohttp.ClientSession() as ses:
            async with ses.get(f"https://api.nitrado.net/services", headers=headers) as e:
                parsed = json.loads(await e.read())
                print(json.dumps(parsed, indent=4))
                dictof = dict(parsed)
                embed = discord.Embed(title="Nitrado Server List", description="Lists your current Nitrado Servers", color=0xE40000)
                c = 0
                for d in dictof['data']['services']:
                    c += 1
                    embed.add_field(name=f'Server # {d["id"]}', value=f"{d['details']['name']}")
                    #for v in (i).values())
                    #    print(v.get('id'))
                await interaction.response.send_message(embed=embed)

    #@app_commands.command(name="link", description="Link username with discord")
    #async def link(self, interaction:discord.Interaction):
    #    pass
       # headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"} # May link this with Economy later
       # async with aiohttp.ClientSession() as ses:
       #      async with ses.get(f"https://api.nitrado.net/services", headers=headers) as e:
       #          parsed = json.loads(await e.read())
       #          print(json.dumps(parsed, indent=4))
       #          dictof = dict(parsed)
       #          embed = discord.Embed(title="Nitrado Server List", description="Lists your current Nitrado Servers")
       #          c = 0
       #          for d in dictof['data']['services']:
       #              c += 1
       #              embed.add_field(name=f'Server # {d["id"]}', value=f"{d['details']['name']}")
       #              #for v in (i).values())
       #              #    print(v.get('id'))
       #          await interaction.response.send_message(embed=embed)
       




    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="generateallheatmap", description="Generates a heatmap with all player movement positions for the log file")
    async def maxkillfeed(self, interaction:discord.Interaction):
        """Generate heatmap with server selection dropdown"""
        s.execute("SELECT * FROM servers")
        servers_list = s.fetchall()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.", ephemeral=True)
            return
        
        async def heatmap_callback(cb_interaction: discord.Interaction, serverid: int):
            await cb_interaction.response.defer()
            fp = path.abspath(
                path.join(path.dirname(__file__), "..", "files", f"{serverid}.ADM")
            )
            playercoords = []
            try:
                async with aiofiles.open(fp, mode="r") as f:
                    async for line in f:
                        coordlog = re.search(r'Player ".*?" \(id=.*? pos=<(\d+\.\d+), (\d+\.\d+), (\d+\.\d+)>\)', line)
                        if coordlog:
                            x, y, _ = list(coordlog.groups())  # Extracting x and y coordinates only
                            playercoords.append((float(x), float(y)))
                generate_heatmap('./utils/y.jpg', playercoords)
                embed = discord.Embed(title="Player Location Heatmap (All)",description=f'Entries: {len(playercoords)}', color=0xE40000).set_image(url="attachment://heatmap.jpg")
                await cb_interaction.followup.send(embed=embed, file=discord.File("heatmap.jpg"))
            except FileNotFoundError:
                await cb_interaction.followup.send(f"Log file not found for server `{serverid}`.", ephemeral=True)
            except Exception as e:
                await cb_interaction.followup.send(f"Error generating heatmap: {str(e)}", ephemeral=True)
        
        class HeatmapServerSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                    for server in servers_list
                ]
                super().__init__(
                    placeholder="Choose a server...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, sel_interaction: discord.Interaction):
                if sel_interaction.user.id != interaction.user.id:
                    await sel_interaction.response.send_message("You are not permitted to do this.", ephemeral=True)
                    return
                
                await heatmap_callback(sel_interaction, int(self.values[0]))
        
        class HeatmapServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(HeatmapServerSelect())
        
        await interaction.response.send_message(
            "Select a server to generate heatmap for:",
            view=HeatmapServerView(),
            ephemeral=True
        )

    @app_commands.command(name="link", description="Links your account with DayZ Underworld bot")
    async def link_account(self, interaction:discord.Interaction, username:str):
        if len(st.execute(f"SELECT * FROM stats WHERE dcid = ?", (interaction.user.id,)).fetchall()) >= 1:
            await interaction.response.send_message("You are already linked to a username!")
        elif len(st.execute(f"SELECT dcid FROM stats WHERE user = ?", (interaction.user.id,)).fetchall()) >= 1:
            await interaction.response.send_message("That username is already linked!")
        elif st.execute(f"SELECT * FROM stats WHERE user = ? COLLATE NOCASE", (username,)).fetchall() == []:
            await interaction.response.send_message("That username is not yet in the database. If it is your first time joining the DayZ server, allow the bot 5-10 minutes to update the database")
        else:
            try:
                username_from_database = st.execute(f"SELECT user FROM stats WHERE user = ? COLLATE NOCASE", (username,)).fetchone()[0]
                st.execute("UPDATE stats SET dcid = ? WHERE user = ?", (interaction.user.id, username_from_database))
                stats.commit()
                await interaction.response.send_message(f"{username_from_database} is now linked to {interaction.user.mention}")
            except Exception as e:
                await interaction.response.send_message("Something went wrong, please open a ticket, or contact staff")
                print(e)

    @app_commands.command(name="stats", description="View your own stats, or someone elses")
    async def stats(self, interaction:discord.Interaction, username:Union[str, None]=None):
        async def gather_data(data_from_database):
            temp_keys = ['user', 'kills', 'deaths', 'alive since', 'death streak', 'kill streak', 'discord ID', 'money', 'bounty']
            temp_keys = [i.title() for i in temp_keys]
            result_dict = dict.fromkeys(temp_keys)
            remove_from_dict = []
            #print("Generating stats")
            for key, value in zip(result_dict.keys(), data_from_database):
                #print(key)
                if key == 'Alive Since':
                    value = f'<t:{value}>'
                if key == 'Kills':
                    value = str(value) + f' (Ranked #{str(data_from_database[-2])})'
                if key == 'Deaths':
                    value = str(value) + f' (Ranked #{str(data_from_database[-1])})'
                if key == 'Discord Id':
                    if value == 0 or value == None:
                        remove_from_dict.append(key)
                if value != None:
                    result_dict[key] = value
            for i in remove_from_dict:
                del result_dict[i]
            embed = discord.Embed(title=f'{data_from_database[0]}\'s Stats', description=f'Stats as of <t:{int(datetime.datetime.now().timestamp())}>', color=0xE40000)
            for i in result_dict:
                value = result_dict.get(i)
                embed.add_field(name=i, value=value)
            return embed
        if username != None:
            #COLLATE NOCASE
            data_result = st.execute("""
    SELECT p1.*,
           (SELECT COUNT(*) 
            FROM stats AS p2
            WHERE p2.kills > p1.kills
           ) + 1 AS KillRank,
           (SELECT COUNT(*) 
            FROM stats AS p3
            WHERE p3.deaths > p1.deaths
           ) + 1 AS DeathRank
    FROM stats AS p1
    WHERE p1.user = ? COLLATE NOCASE;
""", (username,)).fetchall()
            #print(data_from_database[0][9])
            #print(data_from_database)
            if len(data_result) == 0:
                await interaction.response.send_message(f"{username} does not exist in the database. Please check spelling.")
            else:
                await interaction.response.send_message(embed=await gather_data(data_result[0]))
        elif username == None:
            data_from_database = st.execute("""
    SELECT p1.*,
           (SELECT COUNT(*) 
            FROM stats AS p2
            WHERE p2.kills > p1.kills
           ) + 1 AS KillRank,
           (SELECT COUNT(*) 
            FROM stats AS p3
            WHERE p3.deaths > p1.deaths
           ) + 1 AS DeathRank
    FROM stats AS p1
    WHERE p1.dcid = ? COLLATE NOCASE;
""", (interaction.user.id,)).fetchall()
            print(data_from_database)
            if data_from_database == None or data_from_database == []:
                await interaction.response.send_message("You did not specify a username, and you are not linked to an account, please use /link username, or specify a username!")
            else:
                await interaction.response.send_message(embed=await gather_data(data_from_database[0]))
        
    @app_commands.command(name="unlink", description="Unlinks your account with the bot")
    async def unlink(self, interaction:discord.Interaction):
        username = st.execute(f"SELECT * FROM stats WHERE dcid = ?", (interaction.user.id,)).fetchall()
        if len(st.execute(f"SELECT * FROM stats WHERE dcid = ?", (interaction.user.id,)).fetchall()) >= 1:
            username = username[0][0]
            st.execute("UPDATE stats SET dcid = ? WHERE user = ?", (None, username))
            stats.commit()
            await interaction.response.send_message(f"{username} is now unlinked from {interaction.user.mention}")
        else:
            await interaction.response.send_message("You are not linked to an account!")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="staffunlink", description="Forces an unlink")
    async def staffunlink(self, interaction:discord.Interaction, discord_user:Union[discord.Member]):
        dcid = discord_user.id
        username = st.execute(f"SELECT * FROM stats WHERE dcid = ?", (dcid,)).fetchall()
        if len(st.execute(f"SELECT * FROM stats WHERE dcid = ?", (dcid,)).fetchall()) >= 1:
            username = username[0][0]
            st.execute("UPDATE stats SET dcid = ? WHERE dcid = ?", (None, dcid))
            stats.commit()
            await interaction.response.send_message(f"{discord_user.mention} is now unlinked.")
        else:
            await interaction.response.send_message("That user is not linked!")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(database=[
        app_commands.Choice(name="Servers", value='{"db/servers.db": "servers"}'),
        app_commands.Choice(name="Stats", value='{"db/stats.db": "stats"}'),
        app_commands.Choice(name="Flags", value='{"db/region.db": "region"}'),
        app_commands.Choice(name="Guilds", value='{"db": "None"}'),
        ])
    @app_commands.command(name="resetdatabase", description="Reset a given database")
    async def resetdatabase(self, interaction:discord.Interaction, database:app_commands.Choice[str]):
        deserialized = dict(json.loads(database.value))
        v = list(deserialized.values())[0]
        k = list(deserialized.keys())[0]
        print(v)
        print(k)
        if os.path.exists(k):
            if database.name == "Guilds":
                f = []
                for (dirpath, dirnames, filenames) in os.walk('db'):
                    print(filenames)
                    f.append(filenames)
                print(f)
                print("Printed current")
                if len(f) > 1:
                    f = ([i[:-3] for i in f[0] if i[:-3].isdigit()])
                else:
                    f = ([i[:-3] for i in f if i.isdigit()])
                print(f)
                counts = 0
                entries = 0
                for i in f:
                    db = sqlite3.connect(f'db/{i}.db')
                    dbcur = db.cursor()
                    dbcur.execute(f"""UPDATE config SET channelid = NULL""")
                    db.commit()
                    db.close()
                    entries += dbcur.rowcount
                    counts += 1
                embed = discord.Embed(title="Resetting Database(s)",description=f"Deleted {entries} records from {counts} guilds", color=0xE40000)
            else:
                db = sqlite3.connect(k)
                dbcur = db.cursor()
                dbcur.execute(f"""DELETE FROM {v}""")
                db.commit()
                db.close()
                embed = discord.Embed(title="Resetting Database",description=f"Deleted  {dbcur.rowcount} records from {v}", color=0xE40000)
        else:
            embed = discord.Embed(title="Error when finding Database",description=f"Path: {k} Not found, perhaps bot is not initialized. If deleting guild database execute command in the guild", color=0xE40000)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Commands(bot))
