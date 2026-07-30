import json
import os
import aiosqlite
from datetime import datetime

DATABASE = "data/bot.db"


async def initialize():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

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
                username TEXT,
                nickname TEXT,
                session_id TEXT,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
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

        # Migrate views table: add columns that may not exist in older databases.
        for col, definition in [
            ("username",   "TEXT"),
            ("nickname",   "TEXT"),
            ("session_id", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE views ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists

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
    username: str = None,
    nickname: str = None,
    session_id: str = None,
):

    async with aiosqlite.connect(DATABASE) as db:

        await db.execute(
            """
            INSERT INTO views
            (
                message_id,
                viewer_id,
                username,
                nickname,
                session_id,
                viewed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                viewer_id,
                username,
                nickname,
                session_id,
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


async def get_viewer_ids(message_id: int) -> list[int]:

    async with aiosqlite.connect(DATABASE) as db:

        cursor = await db.execute(
            """
            SELECT DISTINCT viewer_id
            FROM views
            WHERE message_id=?
            """,
            (message_id,),
        )

        return [row[0] for row in await cursor.fetchall()]


async def get_user_history(viewer_id: int) -> list[dict]:

    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                v.id,
                v.message_id,
                v.session_id,
                v.viewed_at,
                m.channel_id,
                m.created_at AS message_created_at
            FROM views v
            JOIN messages m ON v.message_id = m.id
            WHERE v.viewer_id = ?
            ORDER BY v.viewed_at DESC
            """,
            (viewer_id,),
        )

        return [dict(row) for row in await cursor.fetchall()]


async def get_recent_messages(channel_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT id, author_id, created_at, message_json
            FROM messages
            WHERE channel_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (channel_id, limit),
        )

        rows = await cursor.fetchall()

    result = []
    for row in rows:
        entry = dict(row)
        entry["message_json"] = json.loads(entry["message_json"])
        result.append(entry)
    return result


async def purge_old_records(days: int) -> int:
    from datetime import timedelta

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        cursor = await db.execute(
            """
            DELETE FROM messages
            WHERE created_at < ?
            """,
            (cutoff,),
        )

        await db.commit()

        return cursor.rowcount
