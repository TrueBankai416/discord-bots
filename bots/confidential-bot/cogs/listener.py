import os

import discord
from discord.ext import commands

import database
from views.confidential import ConfidentialView


def _resolve_mentions(message: discord.Message, bot_id: int | None = None) -> str:
    """Replace raw Discord mention tokens with human-readable names.
    If bot_id is provided, bot mentions are stripped entirely."""
    content = message.content

    for member in message.mentions:
        if bot_id and member.id == bot_id:
            # Remove the bot mention token (and any surrounding whitespace)
            content = content.replace(f"<@{member.id}>", "").replace(f"<@!{member.id}>", "")
        else:
            content = content.replace(f"<@{member.id}>",  f"@{member.display_name}")
            content = content.replace(f"<@!{member.id}>", f"@{member.display_name}")

    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")

    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")

    return content.strip()


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

        # Detect if this message is a reply to a placeholder — if so, notify
        # the original author so they know someone replied to them.
        reply_to_author_id: int | None = None
        reply_to_author_name: str | None = None
        reply_to_message_id: int | None = None
        reply_to_content: str | None = None
        if message.reference and message.reference.message_id:
            try:
                replied_row = await database.get_message_by_placeholder(
                    message.reference.message_id
                )
            except Exception as e:
                print(f"[reply-lookup] DB error for ref {message.reference.message_id}: {e}")
                replied_row = None
            if replied_row:
                reply_to_author_id = replied_row["author_id"]
                reply_member = message.guild.get_member(reply_to_author_id)
                reply_to_author_name = (
                    reply_member.display_name if reply_member
                    else str(reply_to_author_id)
                )
                reply_to_message_id = replied_row["id"]
                raw = replied_row["message_json"].get("content", "").strip()
                reply_to_content = (raw[:80] + "…") if len(raw) > 80 else raw

        # Capture mentions before the message is deleted (exclude the bot itself)
        tagged_members = [m for m in message.mentions if m.id != self.bot.user.id]
        tagged_roles   = list(message.role_mentions)

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
                "content": _resolve_mentions(message, bot_id=self.bot.user.id),
                "original_message_id": str(message.id),
                "author_name": message.author.display_name,
                "attachments": [fn for fn, _ in attachment_bytes],
                "reply_to_author_id": reply_to_author_id,
                "reply_to_author_name": reply_to_author_name,
                "reply_to_message_id": reply_to_message_id,
                "reply_to_content": reply_to_content,
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

        if reply_to_author_id:
            embed.add_field(
                name="↩ Reply to",
                value=f"<@{reply_to_author_id}> · Message #{reply_to_message_id}",
                inline=False,
            )

        if tagged_members or tagged_roles:
            tagged_str = " ".join(
                [m.mention for m in tagged_members]
                + [r.mention for r in tagged_roles]
            )
            embed.add_field(name="Tagged", value=tagged_str, inline=False)

        embed.set_footer(text=f"Message ID: {db_id}")

        view = ConfidentialView(db_id)

        # Include raw mentions in content so Discord sends ping notifications.
        # Always include the original author when this is a reply, so they're notified.
        ping_parts = [m.mention for m in tagged_members] + [r.mention for r in tagged_roles]
        if reply_to_author_id:
            ping_parts.insert(0, f"<@{reply_to_author_id}>")
        ping_content = " ".join(ping_parts) or None

        placeholder = await message.channel.send(
            content=ping_content,
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )

        await database.set_placeholder_message(
            db_id,
            placeholder.id
        )


async def setup(bot):
    await bot.add_cog(Listener(bot))
