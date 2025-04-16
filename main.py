
import discord
from discord.ext import commands
from config import Config
import logging
import asyncio
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.all()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix=Config.BOT_PREFIX,
    description="Test",
    intents = discord.Intents.all(),
)
cogs = [
    'cogs.newkillfeed', 'cogs.commands'
]
logging.debug("Loading cogs...")
@bot.event
async def on_ready():
    print("Bot Ready")
    s = await bot.application_info()
    if s.bot_public == True:
        print("""
              

              ERROR: SECURITY WARNING
Bot is public, this is a security risk as commands are only resistricted to members who have admin access.
For Example, if unauthorized persons were to add the bot to their guild, they would have access to admin commands.
Please turn the bot public to FALSE in application settings. If you need help with this error, contact b0nggo
              
Application closing automatically.                                       
              """)        
        exit()
async def load():
    if __name__ == '__main__':
        for i in cogs:
            await bot.load_extension(i)
            print("Loaded "+ i)

async def main():
    await load()
    await bot.start(Config.DISCORD_TOKEN)

asyncio.run(main())

    