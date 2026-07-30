import json
import aiosqlite
from datetime import datetime

DATABASE = "data/bot.db"


async def initialize():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                message_json TEXT NOT NULL,
                placeholder_message_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                viewer_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY(message_id) REFERENCES messages(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS protected_channels (
                channel_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                watermark INTEGER NOT NULL DEFAULT 1,
                delete_delay REAL NOT NULL DEFAULT 0
            )
        """)

        await db.commit()


async def save_message(
    guild_id: int,
    channel_id: int,
    author_id: int,
    message_data: dict,
) -> int:

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            """
            INSERT INTO messages
            (
                guild_id,
                channel_id,
                author_id,
                created_at,
                message_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                author_id,
                datetime.utcnow().isoformat(),
                json.dumps(message_data),
            ),
        )

        await db.commit()

        return cursor.lastrowid


async def get_message(message_id: int):

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM messages
            WHERE id=?
            """,
            (message_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        message = dict(row)
        message["message_json"] = json.loads(message["message_json"])

        return message


async def get_message_by_placeholder(placeholder_message_id: int):

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM messages
            WHERE placeholder_message_id=?
            """,
            (placeholder_message_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        message = dict(row)
        message["message_json"] = json.loads(message["message_json"])

        return message


async def set_placeholder_message(
    message_id: int,
    placeholder_message_id: int,
):

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            UPDATE messages
            SET placeholder_message_id=?
            WHERE id=?
            """,
            (
                placeholder_message_id,
                message_id,
            ),
        )

        await db.commit()


async def log_view(
    message_id: int,
    viewer_id: int,
):

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            INSERT INTO views
            (
                message_id,
                viewer_id,
                viewed_at
            )
            VALUES (?, ?, ?)
            """,
            (
                message_id,
                viewer_id,
                datetime.utcnow().isoformat(),
            ),
        )

        await db.commit()


async def get_views(message_id: int):

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM views
            WHERE message_id=?
            ORDER BY viewed_at
            """,
            (message_id,),
        )

        return [dict(row) for row in await cursor.fetchall()]


async def add_protected_channel(channel_id: int):

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO protected_channels(channel_id)
            VALUES (?)
            """,
            (channel_id,),
        )

        await db.commit()


async def remove_protected_channel(channel_id: int):

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            DELETE FROM protected_channels
            WHERE channel_id=?
            """,
            (channel_id,),
        )

        await db.commit()


async def is_protected(channel_id: int) -> bool:

    async with aiosqlite.connect(DATABASE) as db:

        cursor = await db.execute(
            """
            SELECT enabled
            FROM protected_channels
            WHERE channel_id=?
            """,
            (channel_id,),
        )

        row = await cursor.fetchone()

        return row is not None


async def get_protected_channels():

    async with aiosqlite.connect(DATABASE) as db:

        cursor = await db.execute(
            """
            SELECT channel_id
            FROM protected_channels
            ORDER BY channel_id
            """
        )

        return [row[0] for row in await cursor.fetchall()]
