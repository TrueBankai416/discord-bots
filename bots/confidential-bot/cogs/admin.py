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


async def setup(bot):
    await bot.add_cog(Admin(bot))
