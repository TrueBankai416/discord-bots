import io
import secrets
import string
import textwrap
from datetime import datetime, timezone

import discord
from PIL import Image, ImageDraw, ImageFont

import database


# ── Image constants ───────────────────────────────────────────────────────────

_BG        = ( 20,  22,  28)
_HEADER_BG = ( 38,  40,  52)
_GOLD      = (200, 170,  50)
_SUBTEXT   = (140, 145, 158)
_BODY      = (210, 215, 220)
_RULE      = ( 50,  55,  70)
_MARK      = ( 70,  75,  85)

_FONT_PATHS = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _session_id() -> str:
    chars = string.ascii_uppercase + string.digits
    return (
        "".join(secrets.choice(chars) for _ in range(4))
        + "-"
        + "".join(secrets.choice(chars) for _ in range(4))
    )


def build_message_image(
    content: str,
    author_name: str,
    viewer_name: str,
    viewer_id: int,
    timestamp: str,
    session_id: str,
) -> io.BytesIO:
    PAD   = 24
    WIDTH = 640
    WRAP  = 72

    f_title = _font(15)
    f_body  = _font(14)
    f_small = _font(12)

    lines = textwrap.wrap(content, width=WRAP) or ["(empty message)"]

    header_h = PAD + 24 + PAD // 2
    meta_h   = 20 + 8
    rule_h   = 8
    body_h   = len(lines) * 22
    foot_h   = rule_h + 8 + 3 * 18
    HEIGHT   = header_h + meta_h + rule_h + 10 + body_h + 10 + foot_h + PAD

    img  = Image.new("RGB", (WIDTH, max(HEIGHT, 220)), _BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (WIDTH, header_h)], fill=_HEADER_BG)
    draw.text((PAD, PAD // 2), "CONFIDENTIAL MESSAGE", font=f_title, fill=_GOLD)

    y = header_h
    draw.text((PAD, y), f"From: {author_name}", font=f_small, fill=_SUBTEXT)
    y += meta_h

    # Separator
    draw.line([(PAD, y), (WIDTH - PAD, y)], fill=_RULE, width=1)
    y += rule_h + 10

    # Message body
    for line in lines:
        draw.text((PAD, y), line, font=f_body, fill=_BODY)
        y += 22

    y += 10

    # Separator
    draw.line([(PAD, y), (WIDTH - PAD, y)], fill=_RULE, width=1)
    y += rule_h + 8

    # Watermark footer
    draw.text((PAD, y), f"Viewed by: {viewer_name}  |  ID: {viewer_id}", font=f_small, fill=_MARK)
    y += 18
    draw.text((PAD, y), f"Time: {timestamp} UTC", font=f_small, fill=_MARK)
    y += 18
    draw.text((PAD, y), f"Session: {session_id}", font=f_small, fill=_MARK)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ── View components ───────────────────────────────────────────────────────────

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
        session_id = _session_id()
        viewer     = interaction.user
        username   = viewer.name
        nickname   = getattr(viewer, "nick", None) or viewer.display_name
        timestamp  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        await database.log_view(
            message_id=self.message_id,
            viewer_id=viewer.id,
            username=username,
            nickname=nickname,
            session_id=session_id,
        )

        message = await database.get_message(self.message_id)

        if message is None:
            await interaction.response.send_message(
                "❌ This message no longer exists.",
                ephemeral=True,
            )
            return

        data        = message["message_json"]
        content     = data.get("content", "")
        author_name = data.get("author_name", f"User {message['author_id']}")

        buf = build_message_image(
            content=content,
            author_name=author_name,
            viewer_name=f"{nickname} ({username})",
            viewer_id=viewer.id,
            timestamp=timestamp,
            session_id=session_id,
        )

        await interaction.response.send_message(
            file=discord.File(buf, filename="confidential.png"),
            ephemeral=True,
        )


class ConfidentialView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)

        self.add_item(
            ViewMessageButton(message_id)
        )
