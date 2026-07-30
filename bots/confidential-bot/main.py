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

        # Sync slash commands globally so they work in every guild the bot joins.
        # Global sync can take up to 1 hour to propagate; guild sync is instant
        # but only works for the one guild. To force instant sync on your dev
        # guild during testing, uncomment the three lines below.
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} commands globally")

        # --- Dev guild instant-sync (uncomment for faster testing) ---
        # guild = discord.Object(id=GUILD_ID)
        # self.tree.copy_global_to(guild=guild)
        # await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print()

        print("Connected Guilds:")
        for guild in self.guilds:
            print(f"  {guild.name} ({guild.id})")


bot = ConfidentialBot()

bot.run(TOKEN)
