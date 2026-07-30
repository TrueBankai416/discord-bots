import io
import os
import secrets
import string
import textwrap
from datetime import datetime, timezone

import emoji as emoji_lib
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

_EMOJI_FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoEmoji-VariableFont_wght.ttf",
    "/usr/share/fonts/noto/NotoEmoji-Regular.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _emoji_font(size: int):
    for path in _EMOJI_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return None


def _draw_with_emoji(draw, xy, text, main_font, e_font, fill):
    """Render text, switching to e_font for emoji sequences."""
    x, y = xy
    if not e_font:
        draw.text((x, y), text, font=main_font, fill=fill)
        return

    segments = []
    last = 0
    for item in emoji_lib.emoji_list(text):
        s, e = item["match_start"], item["match_end"]
        if last < s:
            segments.append((text[last:s], False))
        segments.append((text[s:e], True))
        last = e
    if last < len(text):
        segments.append((text[last:], False))

    for seg, is_emoji in segments:
        font = e_font if is_emoji else main_font
        draw.text((x, y), seg, font=font, fill=fill)
        x += font.getlength(seg)


def _session_id() -> str:
    chars = string.ascii_uppercase + string.digits
    return (
        "".join(secrets.choice(chars) for _ in range(4))
        + "-"
        + "".join(secrets.choice(chars) for _ in range(4))
    )


def _diagonal_watermark(img: Image.Image, text: str, alpha: int = 18) -> Image.Image:
    """Tile `text` diagonally across the entire image at near-invisible opacity."""
    base = img.convert("RGBA")
    w, h = base.size

    # Large enough canvas that rotation doesn't clip any corner
    diag = int((w * w + h * h) ** 0.5) + 20

    overlay = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    font    = _font(11)

    step_x, step_y = 210, 52
    for row_y in range(0, diag, step_y):
        # Offset alternating rows so the grid doesn't look too regular
        offset = (step_x // 2) if (row_y // step_y) % 2 else 0
        for row_x in range(-step_x + offset, diag + step_x, step_x):
            draw.text((row_x, row_y), text, font=font, fill=(200, 200, 200, alpha))

    overlay = overlay.rotate(32)

    # Crop back to original dimensions, centred
    cx = (diag - w) // 2
    cy = (diag - h) // 2
    overlay = overlay.crop((cx, cy, cx + w, cy + h))

    base = Image.alpha_composite(base, overlay)
    return base.convert("RGB")


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
    f_emoji = _emoji_font(14)

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
        _draw_with_emoji(draw, (PAD, y), line, f_body, f_emoji, _BODY)
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

    # Diagonal repeating watermark embedded across the whole image.
    # Barely visible at normal brightness; survives cropping the footer.
    img = _diagonal_watermark(img, text=f"{viewer_id}  •  {session_id}")

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

        files = [discord.File(buf, filename="confidential.png")]

        # Re-attach any files that were saved when the original was deleted
        att_dir = os.path.join("data", "attachments", str(self.message_id))
        if os.path.isdir(att_dir):
            for filename in sorted(os.listdir(att_dir)):
                try:
                    files.append(discord.File(os.path.join(att_dir, filename), filename=filename))
                except Exception as e:
                    print(f"Failed to attach {filename}: {e}")

        await interaction.response.send_message(
            files=files,
            ephemeral=True,
        )


class ConfidentialView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)

        self.add_item(
            ViewMessageButton(message_id)
        )
