import discord
import database


class ViewMessageButton(discord.ui.DynamicItem[discord.ui.Button], template=r"view:(?P<message_id>\d+)"):
    def __init__(self, message_id: int):
        super().__init__(
            discord.ui.Button(
                label="👁 View",
                style=discord.ButtonStyle.primary,
                custom_id=f"view:{message_id}",
            )
        )

        self.message_id = message_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match,
    ):
        return cls(int(match["message_id"]))

    async def callback(self, interaction: discord.Interaction):

        await database.log_view(
            self.message_id,
            interaction.user.id,
        )

        message = await database.get_message(self.message_id)

        if message is None:
            await interaction.response.send_message(
                "❌ This message no longer exists.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🔒 Confidential Message",
            description=message["content"],
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Author",
            value=f"<@{message['author_id']}>",
            inline=False,
        )

        embed.set_footer(
            text=f"Message #{self.message_id}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


class ConfidentialView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)

        self.add_item(
            ViewMessageButton(message_id)
        )
