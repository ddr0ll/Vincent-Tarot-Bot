import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

load_dotenv()
TOKEN = os.getenv('TOKEN')

class Vincent(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=[], intents=intents)

        self.cogslist = ['cogs.tarot', 'cogs.docs']

    async def setup_hook(self):
        for cog in self.cogslist:
            await self.load_extension(cog)

        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} commands')
        except Exception as e:
            print(f"Error:\n{e}")

    async def on_ready(self):
        print(f"Logged in as {self.user}")

bot = Vincent()

@bot.tree.error
async def cog_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Подождите {error.retry_after:.1f}s перед следующим вызовом"
        print("Cooldown error")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    else:
        print(f'the error was: {error}')

bot.run(TOKEN)

