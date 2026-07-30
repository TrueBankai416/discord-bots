import discord
from discord.ext import commands

import database
from views.confidential import ConfidentialView


class Listener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # Ignore bots
        if message.author.bot:
            return

        # Ignore DMs
        if message.guild is None:
            return

        # Ignore unprotected channels
        if not await database.is_protected(message.channel.id):
            return

        # Save the message
        db_id = await database.save_message(
            author_id=message.author.id,
            channel_id=message.channel.id,
            content=message.content,
            original_message_id=message.id,
        )

        # Delete the original
        try:
            await message.delete()
        except discord.Forbidden:
            print("Missing Manage Messages permission.")
            return
        except discord.HTTPException:
            print("Failed to delete message.")
            return

        embed = discord.Embed(
            title="🔒 Confidential Message",
            description=(
                f"Posted by {message.author.mention}\n\n"
                "Click **👁 View** below to read the message."
            ),
            color=discord.Color.gold(),
        )

        embed.set_footer(text=f"Message ID: {db_id}")

        view = ConfidentialView(db_id)

        placeholder = await message.channel.send(
            embed=embed,
            view=view
        )

        await database.set_placeholder_message(
            db_id,
            placeholder.id
        )


async def setup(bot):
    await bot.add_cog(Listener(bot))
