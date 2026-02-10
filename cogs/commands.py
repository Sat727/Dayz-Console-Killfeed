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

# Initialize consolidated database
from utils import killfeed_database
killfeed_database.initialize_master_db()

# Wrapper functions for backward compatibility
def is_device_id_banned(device_id):
    return killfeed_database.is_device_id_banned(device_id)

def get_device_id_from_stats(username):
    return killfeed_database.get_device_id_from_stats(username)

def get_all_banned_users():
    return killfeed_database.get_all_banned_users()

def unban_device_id(device_id):
    killfeed_database.unban_device_id(device_id)
    

categories = ("Build", "Death", "Kill", "Hit", "Heatmap", "BaseInteraction", "OnlineCount", 'DeathCount', 'KillCount', "BanNotification", "Connect", "Disconnect")

def updateDatabase(categories=categories):
    """Initialize config categories in the master database."""
    try:
        # Get all registered servers
        servers_list = killfeed_database.get_servers()
        
        # Initialize all config categories for each server
        if servers_list:
            for server in servers_list:
                server_id = str(server[0])
                for category in categories:
                    killfeed_database.insert_config(server_id, category)
        print("Database config initialized successfully")
    except Exception as e:
        print(f"Error initializing database config: {e}")

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
        servers_list = killfeed_database.get_servers()
        
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
            await interaction.response.send_message("You are not permitted to do this.")
            return
        
        if self.values[0] == "none":
            await interaction.response.send_message("No servers are configured. Use `/nitradoserver` to add one.")
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
            await interaction.response.send_message("You are not allowed to interact with this menu.")
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
        regions = killfeed_database.get_regions()
        if len(regions) > 25:
            await interaction.response.send_message("You have more than 25 events. The limit is 25")
        else:
            killfeed_database.insert_region(x_coord, z_coord, radius, channel.id, name)
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
            conn = killfeed_database.get_connection()
            cursor = conn.cursor()
            for i in self.lastbatch:
                cursor.execute("DELETE FROM codes WHERE code = ?", (i,))
                count += 1
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"Deleted {count} entries")
            self.lastbatch = []
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
                killfeed_database.insert_device_ban("Unknown", device_id)
                await interaction.response.send_message(f"Successfully banned Device ID {device_id}.")
        elif username:
            device_id = get_device_id_from_stats(username)
            if device_id:
                if is_device_id_banned(device_id):
                    await interaction.response.send_message(f"Device ID {device_id} associated with {username} is already banned.")
                else:
                    killfeed_database.insert_device_ban(username, device_id)
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
        conn = killfeed_database.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM codes WHERE batchid = ?", (batchid,))
        rowcount = cursor.rowcount
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"Terminated {rowcount} codes from the database")

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
                        conn = killfeed_database.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT code FROM codes")
                        memory_db = [code[0] for code in cursor.fetchall()]
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
                            cursor.execute("INSERT INTO codes (code, data, redeemed, batchid) VALUES (?,?,?,?)", (raw_code, value.value, 1, batchid))
                            raw_string += '\n'
                        self.lastbatch = batch
                        conn.commit()
                        conn.close()
                        embed = discord.Embed(title=f"Generated {amount} {value.name} Keys", description=f'```\n{raw_string+"```"}', color=0xE40000).set_footer(text=f'Batch ID: {batchid}')
                        await choice.response.send_message(embed=embed)
                        await choice.message.delete()
                    except Exception as e:
                        print(e)
                elif choice.data.get('custom_id') == "1":
                    await choice.response.send_message("Aborted key generation")
                    await choice.message.delete()
            else:
                print("Unauthorized button use")
                await choice.response.send_message("You do not have permission to select this!")
        no_button.callback = selection
        yes_button.callback = selection
        views.add_item(no_button)
        await interaction.response.send_message(f'Are you sure you want to generate {amount} {value.value} keys?',view=views)


    @app_commands.command(name="redeem", description="Redeem keys")
    async def redeem(self, interaction:discord.Interaction):
        servers_list = killfeed_database.get_servers()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.")
            return
        
        class ServerSelect(discord.ui.Select):
            def __init__(inner_self):
                options = [
                    discord.SelectOption(label=f"Server {server[0]}", value=str(server[0]))
                    for server in servers_list
                ]
                super().__init__(
                    placeholder="Choose a server to redeem on...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(inner_self, select_interaction: discord.Interaction):
                if select_interaction.user.id != interaction.user.id:
                    await select_interaction.response.send_message("You are not permitted to do this.")
                    return
                
                selected_server_id = int(inner_self.values[0])
                
                class Redeem(discord.ui.Modal, title='Key Redemption'):
                    username = discord.ui.TextInput(label='Username', required=True, style=discord.TextStyle.short, max_length=16, min_length=3)
                    code = discord.ui.TextInput(label='Code', required=True, max_length=29, min_length=29, style=discord.TextStyle.long)
                    
                    async def on_submit(modal_self, modal_interaction: discord.Interaction):
                        conn = killfeed_database.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM codes WHERE code=?", (str(modal_self.code),))
                        query = cursor.fetchall()
                        if len(query) == 1:
                            if query[0][3] == 1:  # redeemed column is at index 3 now
                                if re.compile(r'[a-zA-Z0-9-_]*$').match(str(modal_self.username)):
                                    cursor.execute("SELECT code FROM codes WHERE code = ?", (str(modal_self.code),))
                                    rows = cursor.fetchall()
                                    print(rows)
                                    if len(rows) > 0:
                                        try:
                                            with open('logs/audit.txt', 'a') as log:
                                                log.write(f'{modal_interaction.user} ({modal_interaction.user.id}) Redeemed code in {modal_interaction.channel.name} ({modal_interaction.channel.id}) for username {modal_self.username} at {datetime.datetime.now().strftime("%m/%d/%Y, %I:%M %p")}\n')
                                                print("Passed x1")
                                        except Exception as e:
                                            print(e)
                                        data = str(await Nitrado.Priority(id=selected_server_id, username=modal_self.username, priority='Add'))
                                        print(data)
                                        if data.startswith("Successful"):
                                            cursor.execute("UPDATE codes SET redeemed = ?, user = ? WHERE code = ?", (0, str(modal_self.username), str(modal_self.code)))
                                            conn.commit()
                                            conn.close()
                                            await modal_interaction.response.send_message(f"✓ Redeemed {query[0][2]} for {modal_self.username} on server {selected_server_id}")  # data column is at index 2
                                        else:
                                            conn.close()
                                            await modal_interaction.response.send_message(data)
                                else:
                                    await modal_interaction.response.send_message("Invalid username. Please try again!")
                            elif query[0][2] == 0:
                                await modal_interaction.response.send_message("Code already redeemed!")
                        else:
                            await modal_interaction.response.send_message("Invalid code!")
                
                await select_interaction.response.send_modal(Redeem())
        
        class ServerSelectView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(ServerSelect())
        
        await interaction.response.send_message(
            "Select a server to redeem your key on:",
            view=ServerSelectView()
        )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="removearea", description="Remove a flag listener")
    async def removearea(self, interaction:discord.Interaction):
        rows = killfeed_database.get_regions()
        select = discord.ui.Select()
        select.placeholder = "Which area would you like to remove?"
        c = 0
        if rows == []:
            await interaction.response.send_message("No areas to remove. Create one using /addarea")
            return
        
        region_data = {}
        for i in rows:
            c += 1
            region_name = i[-1]
            region_data[c] = region_name
            select.add_option(label=f"{region_name}", description=f"X:{i[0]}, Z:{i[1]}", value=str(c))
        
        select.max_values = 1
        view = discord.ui.View()
        view.add_item(select)
        
        async def callback(select_interaction: discord.Interaction):
            selected_idx = int(select.values[0])
            region_name = region_data[selected_idx]
            
            conn = killfeed_database.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM region WHERE name = ?", (region_name,))
            conn.commit()
            conn.close()
            
            await select_interaction.response.send_message(f"Deleted {region_name} from your listeners")
            view.stop()
        
        select.callback = callback
        r = await interaction.response.send_message(view=view)
        await view.wait()

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
        servers_list = killfeed_database.get_servers()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.")
            return
        
        async def banlist_callback(cb_interaction: discord.Interaction, server_id: int):
            await cb_interaction.response.defer()
            data = await Nitrado.banPlayer(id=server_id, username=username, ban=action)
            # Convert bytes to string if necessary
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            # Ensure data is not empty
            message = data if data else "Ban action completed."
            await cb_interaction.message.edit(content=f" {message}", view=None)
        
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
                    await sel_interaction.response.send_message("You are not permitted to do this.")
                    return
                
                await banlist_callback(sel_interaction, int(self.values[0]))
        
        class BanListServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(BanListServerSelect())
        
        await interaction.response.send_message(
            f"Select a server to manage banlist for **{username}** (Action: {action.name}):",
            view=BanListServerView()
        )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="Add someone"),
        app_commands.Choice(name="Remove", value="Remove someone"),
        ])
    @app_commands.command(name="priority", description="Priority Options")
    async def priority(self, interaction:discord.Interaction, username:str, action:app_commands.Choice[str]):
        """Priority management with server selection dropdown"""
        servers_list = killfeed_database.get_servers()
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.")
            return
        
        async def priority_callback(cb_interaction: discord.Interaction, server_id: int):
            await cb_interaction.response.defer()
            data = await Nitrado.Priority(id=server_id, username=username, priority=action)
            # Convert bytes to string if necessary
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            # Ensure data is not empty
            message = data if data else "Priority action completed."
            await cb_interaction.message.edit(content=f" {message}", view=None)
        
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
                    await sel_interaction.response.send_message("You are not permitted to do this.")
                    return
                
                await priority_callback(sel_interaction, int(self.values[0]))
        
        class PriorityServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(PriorityServerSelect())
        
        await interaction.response.send_message(
            f"Select a server to manage priority for **{username}** (Action: {action.name}):",
            view=PriorityServerView()
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
        servers_list = killfeed_database.get_servers()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.")
            return
        
        async def select_category_callback(ctx_interaction: discord.Interaction, server_id: int, category: str):
            """Callback for when user selects a category"""
            # Create a channel select view
            async def select_channel_callback(final_interaction: discord.Interaction, channel: discord.TextChannel | discord.VoiceChannel):
                """Callback for when user selects a channel"""
                await final_interaction.response.defer()
                killfeed_database.update_config(str(server_id), category, channel.id)
                await final_interaction.message.edit(
                    content=f"Updated server `{server_id}` to send `{category}` logs to {channel.mention}",
                    view=None
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
                        await ch_interaction.response.send_message("You are not allowed to interact with this menu.")
                        return
                    await select_channel_callback(ch_interaction, self.select_channel.values[0])
            
            await ctx_interaction.response.defer()
            await ctx_interaction.message.edit(
                content=f"Select a channel for `{category}` logs:",
                view=ChannelView()
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
                    await sel_interaction.response.send_message("You are not allowed to interact with this menu.")
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
                            await cat_interaction.response.send_message("You are not allowed to interact with this menu.")
                            return
                        
                        await select_category_callback(cat_interaction, server_id, self.values[0])
                
                class CategorySelectView(discord.ui.View):
                    def __init__(self):
                        super().__init__()
                        self.add_item(CategorySelect())
                
                await sel_interaction.response.defer()
                await sel_interaction.message.edit(
                    content=f"Select a log category for server `{server_id}`:",
                    view=CategorySelectView()
                )
        
        class ServerSelectViewForLogConfig(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(ServerSelectForLogConfig())
        
        await interaction.response.send_message(
            "Select a server to configure:",
            view=ServerSelectViewForLogConfig()
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
                        await modal_interaction.response.send_message("You are not allowed to submit this form.")
                        return
                    
                    try:
                        nitradoserver = int(self.server_id.value)
                    except ValueError:
                        await modal_interaction.response.send_message("Server ID must be a number.")
                        return
                    
                    servers_list = killfeed_database.get_servers()
                    r = servers_list
                    
                    try:
                        if nitradoserver not in [i[0] for i in r]:
                            # Initialize config for new server
                            for category in categories:
                                killfeed_database.insert_config(str(nitradoserver), category)
                            killfeed_database.insert_server(str(nitradoserver))
                            await modal_interaction.response.send_message(f"Initialized server `{nitradoserver}`\nUse `/logconfig` to configure the server.")
                        else:
                            await modal_interaction.response.send_message("This nitrado server already exists in the database.")
                    except Exception as e:
                        # Initialize config for new server if error
                        for category in categories:
                            killfeed_database.insert_config(str(nitradoserver), category)
                        killfeed_database.insert_server(str(nitradoserver))
                        await modal_interaction.response.send_message(f"Initialized server `{nitradoserver}`\nUse `/logconfig` to configure the server.")
            
            await interaction.response.send_modal(AddServerModal())
        
        elif action.name == "Remove":
            # For removing, use a dropdown
            servers_list = killfeed_database.get_servers()
            
            if not servers_list:
                await interaction.response.send_message("No servers in the database to remove.")
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
                        await sel_interaction.response.send_message("You are not allowed to interact with this menu.")
                        return
                    
                    await sel_interaction.response.defer()
                    server_id = int(self.values[0])
                    
                    try:
                        os.remove(f"db/{server_id}.db")
                        conn = killfeed_database.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM servers WHERE serverid = ?", (server_id,))
                        conn.commit()
                        conn.close()
                        await sel_interaction.message.edit(
                            content=f"Removed server `{server_id}` from the database.",
                            view=None
                        )
                    except Exception as e:
                        await sel_interaction.message.edit(
                            content=f"Error removing server: {str(e)}",
                            view=None
                        )
            
            class RemoveServerView(discord.ui.View):
                def __init__(self):
                    super().__init__()
                    self.add_item(RemoveServerSelect())
            
            await interaction.response.send_message(
                "Select a server to remove:",
                view=RemoveServerView(),
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
        servers_list = killfeed_database.get_servers()
        
        if not servers_list:
            await interaction.response.send_message("No servers added to the database. Use `/nitradoserver` to add one.")
            return
        
        async def heatmap_callback(cb_interaction: discord.Interaction, serverid: int):
            await cb_interaction.response.defer()
            await cb_interaction.message.edit(content=f"Generating heatmap for server `{serverid}`...", view=None)
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
                await cb_interaction.message.edit(content=f"Heatmap generated for server `{serverid}`")
            except FileNotFoundError:
                await cb_interaction.message.edit(content=f" Log file not found for server `{serverid}`.")
            except Exception as e:
                await cb_interaction.message.edit(content=f" Error generating heatmap: {str(e)}")
        
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
                    await sel_interaction.response.send_message("You are not permitted to do this.")
                    return
                
                await heatmap_callback(sel_interaction, int(self.values[0]))
        
        class HeatmapServerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(HeatmapServerSelect())
        
        await interaction.response.send_message(
            "Select a server to generate heatmap for:",
            view=HeatmapServerView()
        )

    @app_commands.command(name="link", description="Links your account with DayZ Underworld bot")
    async def link_account(self, interaction:discord.Interaction, username:str):
        conn = killfeed_database.get_connection()
        cursor = conn.cursor()
        
        # Check if already linked
        cursor.execute("SELECT * FROM stats WHERE dcid = ?", (interaction.user.id,))
        if len(cursor.fetchall()) >= 1:
            conn.close()
            await interaction.response.send_message("You are already linked to a username!")
            return
        
        # Check if username already linked
        cursor.execute("SELECT dcid FROM stats WHERE dcid = ?", (interaction.user.id,))
        if len(cursor.fetchall()) >= 1:
            conn.close()
            await interaction.response.send_message("That username is already linked!")
            return
        
        # Check if username exists
        cursor.execute("SELECT * FROM stats WHERE user = ? COLLATE NOCASE", (username,))
        if cursor.fetchall() == []:
            conn.close()
            await interaction.response.send_message("That username is not yet in the database. If it is your first time joining the DayZ server, allow the bot 5-10 minutes to update the database")
            return
        
        try:
            cursor.execute("SELECT user FROM stats WHERE user = ? COLLATE NOCASE", (username,))
            username_from_database = cursor.fetchone()[0]
            cursor.execute("UPDATE stats SET dcid = ? WHERE user = ?", (interaction.user.id, username_from_database))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"{username_from_database} is now linked to {interaction.user.mention}")
        except Exception as e:
            conn.close()
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
            conn = killfeed_database.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
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
""", (username,))
            data_result = cursor.fetchall()
            conn.close()
            if len(data_result) == 0:
                await interaction.response.send_message(f"{username} does not exist in the database. Please check spelling.")
            else:
                await interaction.response.send_message(embed=await gather_data(data_result[0]))
        elif username == None:
            conn = killfeed_database.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
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
""", (interaction.user.id,))
            data_from_database = cursor.fetchall()
            conn.close()
            print(data_from_database)
            if data_from_database == None or data_from_database == []:
                await interaction.response.send_message("You did not specify a username, and you are not linked to an account, please use /link username, or specify a username!")
            else:
                await interaction.response.send_message(embed=await gather_data(data_from_database[0]))
        
    @app_commands.command(name="unlink", description="Unlinks your account with the bot")
    async def unlink(self, interaction:discord.Interaction):
        conn = killfeed_database.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM stats WHERE dcid = ?", (interaction.user.id,))
        username_data = cursor.fetchall()
        
        if len(username_data) >= 1:
            username = username_data[0][1]
            cursor.execute("UPDATE stats SET dcid = ? WHERE user = ?", (None, username))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"{username} is now unlinked from {interaction.user.mention}")
        else:
            conn.close()
            await interaction.response.send_message("You are not linked to an account!")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="staffunlink", description="Forces an unlink")
    async def staffunlink(self, interaction:discord.Interaction, discord_user:Union[discord.Member]):
        conn = killfeed_database.get_connection()
        cursor = conn.cursor()
        dcid = discord_user.id
        
        cursor.execute("SELECT * FROM stats WHERE dcid = ?", (dcid,))
        username_data = cursor.fetchall()
        
        if len(username_data) >= 1:
            username = username_data[0][1]
            cursor.execute("UPDATE stats SET dcid = ? WHERE dcid = ?", (None, dcid))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"{discord_user.mention} is now unlinked.")
        else:
            conn.close()
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
