import os

import discord
from discord.ext import commands

import database
from views.confidential import ConfidentialView


def _resolve_mentions(message: discord.Message) -> str:
    """Replace raw Discord mention tokens with human-readable names."""
    content = message.content

    for member in message.mentions:
        content = content.replace(f"<@{member.id}>",  f"@{member.display_name}")
        content = content.replace(f"<@!{member.id}>", f"@{member.display_name}")

    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")

    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")

    return content


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

        # Ignore messages with no text (images, GIFs, stickers, etc.)
        if not message.content or not message.content.strip():
            return

        # Download any attachments before the message is deleted
        attachment_bytes: list[tuple[str, bytes]] = []
        for att in message.attachments:
            try:
                attachment_bytes.append((att.filename, await att.read()))
            except Exception as e:
                print(f"Failed to download attachment {att.filename}: {e}")

        # Save the message
        db_id = await database.save_message(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            message_data={
                "content": _resolve_mentions(message),
                "original_message_id": str(message.id),
                "author_name": message.author.display_name,
                "attachments": [fn for fn, _ in attachment_bytes],
            },
        )

        # Persist attachments to disk now that we have the db_id
        if attachment_bytes:
            att_dir = os.path.join("data", "attachments", str(db_id))
            os.makedirs(att_dir, exist_ok=True)
            for filename, data in attachment_bytes:
                with open(os.path.join(att_dir, filename), "wb") as fh:
                    fh.write(data)

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
