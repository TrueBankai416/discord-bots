import discord
from discord.ext import commands

from config import TOKEN, GUILD_ID
import database
from views.confidential import ViewMessageButton


class ConfidentialBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        # Initialize database
        await database.initialize()

        # Load cogs
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.listener")

        # Register persistent dynamic button
        self.add_dynamic_items(ViewMessageButton)

        # Sync slash commands to development guild
        guild = discord.Object(id=GUILD_ID)

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)

        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print()

        print("Connected Guilds:")
        for guild in self.guilds:
            print(f"  {guild.name} ({guild.id})")


bot = ConfidentialBot()

bot.run(TOKEN)
