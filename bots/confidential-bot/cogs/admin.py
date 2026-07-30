import csv
import io

import discord
from discord.ext import commands
from discord import app_commands

import database


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="protect",
        description="Protect a channel."
    )
    async def protect(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        print(f"/protect called by {interaction.user} for {channel.name}")

        await database.add_protected_channel(channel.id)

        await interaction.response.send_message(
            f"🔒 {channel.mention} is now protected.",
            ephemeral=True
        )

    @app_commands.command(
        name="unprotect",
        description="Remove protection from a channel."
    )
    async def unprotect(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        await database.remove_protected_channel(channel.id)

        await interaction.response.send_message(
            f"🔓 {channel.mention} is no longer protected.",
            ephemeral=True
        )

    @app_commands.command(
        name="protected",
        description="List protected channels."
    )
    async def protected(
        self,
        interaction: discord.Interaction
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        channels = await database.get_protected_channels()

        if not channels:
            await interaction.response.send_message(
                "No protected channels.",
                ephemeral=True
            )
            return

        lines = []

        for channel_id in channels:
            channel = interaction.guild.get_channel(channel_id)

            if channel:
                lines.append(f"• {channel.mention}")
            else:
                lines.append(f"• Unknown Channel ({channel_id})")

        embed = discord.Embed(
            title="🔒 Protected Channels",
            description="\n".join(lines),
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


    @app_commands.command(
        name="views",
        description="Show who has viewed a confidential message."
    )
    async def views(
        self,
        interaction: discord.Interaction,
        message_id: int,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        record = await database.get_message(message_id)
        if record is None:
            await interaction.response.send_message(
                f"❌ No message found with ID `{message_id}`.",
                ephemeral=True
            )
            return

        view_records = await database.get_views(message_id)

        if not view_records:
            await interaction.response.send_message(
                f"Nobody has viewed message `#{message_id}` yet.",
                ephemeral=True
            )
            return

        lines = []
        for i, v in enumerate(view_records, 1):
            nick = v.get("nickname") or v.get("username") or f"<@{v['viewer_id']}>"
            ts   = v["viewed_at"][:16].replace("T", " ")
            sid  = v.get("session_id") or "—"
            lines.append(f"`{i}.` {nick} — {ts} UTC `[{sid}]`")

        embed = discord.Embed(
            title=f"🔒 Message #{message_id} — Viewers ({len(view_records)})",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unread",
        description="List guild members who have NOT viewed a confidential message."
    )
    async def unread(
        self,
        interaction: discord.Interaction,
        message_id: int,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        record = await database.get_message(message_id)
        if record is None:
            await interaction.response.send_message(
                f"❌ No message found with ID `{message_id}`.",
                ephemeral=True
            )
            return

        viewer_ids = set(await database.get_viewer_ids(message_id))
        unread_members = [
            m for m in interaction.guild.members
            if not m.bot and m.id not in viewer_ids
        ]

        if not unread_members:
            await interaction.response.send_message(
                f"✅ Everyone has viewed message `#{message_id}`.",
                ephemeral=True
            )
            return

        lines = [f"• {m.mention} ({m.display_name})" for m in unread_members]

        embed = discord.Embed(
            title=f"👁 Message #{message_id} — Unread ({len(unread_members)})",
            description="\n".join(lines[:20])
                + (f"\n… and {len(lines) - 20} more" if len(lines) > 20 else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="history",
        description="Show all confidential messages a member has viewed."
    )
    async def history(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        records = await database.get_user_history(member.id)

        if not records:
            await interaction.response.send_message(
                f"{member.mention} has not viewed any confidential messages.",
                ephemeral=True
            )
            return

        lines = []
        for r in records[:20]:
            channel = interaction.guild.get_channel(r["channel_id"])
            ch_str  = channel.mention if channel else f"(#{r['channel_id']})"
            ts      = r["viewed_at"][:16].replace("T", " ")
            lines.append(f"• Message `#{r['message_id']}` in {ch_str} — {ts} UTC")

        embed = discord.Embed(
            title=f"📋 View History — {member.display_name} ({len(records)} views)",
            description="\n".join(lines)
                + (f"\n… and {len(records) - 20} more" if len(records) > 20 else ""),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="export",
        description="Export the view log for a confidential message as a CSV."
    )
    async def export(
        self,
        interaction: discord.Interaction,
        message_id: int,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        record = await database.get_message(message_id)
        if record is None:
            await interaction.response.send_message(
                f"❌ No message found with ID `{message_id}`.",
                ephemeral=True
            )
            return

        view_records = await database.get_views(message_id)

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["message_id", "viewer_id", "username", "nickname", "viewed_at", "session_id"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for v in view_records:
            writer.writerow({**v, "message_id": message_id})

        buf.seek(0)
        file = discord.File(
            io.BytesIO(buf.getvalue().encode()),
            filename=f"views_message_{message_id}.csv"
        )
        await interaction.response.send_message(
            f"📄 Export for message `#{message_id}` — {len(view_records)} view(s).",
            file=file,
            ephemeral=True
        )

    @app_commands.command(
        name="roster",
        description="List all members with their user IDs and nicknames."
    )
    async def roster(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        members = sorted(
            [m for m in interaction.guild.members if not m.bot],
            key=lambda m: m.display_name.lower()
        )

        # Build CSV for large guilds; embed for small ones
        if len(members) > 30:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "username", "display_name"])
            for m in members:
                writer.writerow([m.id, m.name, m.display_name])
            buf.seek(0)
            file = discord.File(
                io.BytesIO(buf.getvalue().encode()),
                filename="roster.csv"
            )
            await interaction.response.send_message(
                f"📋 {len(members)} members.",
                file=file,
                ephemeral=True
            )
        else:
            lines = [
                f"`{m.id}` — **{m.display_name}** ({m.name})"
                for m in members
            ]
            embed = discord.Embed(
                title=f"📋 Member Roster ({len(members)})",
                description="\n".join(lines),
                color=discord.Color.blurple()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="purge",
        description="Delete confidential message records older than N days."
    )
    async def purge(
        self,
        interaction: discord.Interaction,
        days: int,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        if days < 1:
            await interaction.response.send_message(
                "❌ Days must be at least 1.",
                ephemeral=True
            )
            return

        deleted = await database.purge_old_records(days)

        await interaction.response.send_message(
            f"🗑 Purged **{deleted}** message record(s) older than {days} day(s).",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
