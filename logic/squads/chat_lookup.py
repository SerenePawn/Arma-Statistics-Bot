import asyncpg

_columns_cache: dict[str, set[str]] = {}


async def table_columns(conn: asyncpg.Connection, table: str) -> set[str]:
    if table in _columns_cache:
        return _columns_cache[table]

    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = $1
        """,
        table,
    )
    _columns_cache[table] = {row["column_name"] for row in rows}
    return _columns_cache[table]


async def get_squad_id_by_telegram_chat_id(conn: asyncpg.Connection, chat_id: int) -> int | None:
    squad_cols = await table_columns(conn, "squads")
    chat_id_str = str(chat_id)

    if "telegram_chat_id" in squad_cols:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM squads
            WHERE telegram_chat_id = $1
            ORDER BY id
            LIMIT 1
            """,
            chat_id_str,
        )
    elif "chatters_id" in squad_cols and await table_columns(conn, "chatters"):
        row = await conn.fetchrow(
            """
            SELECT s.id
            FROM squads AS s
                JOIN chatters AS c ON c.id = s.chatters_id
            WHERE c.telegram_chat_id = $1
            ORDER BY s.id
            LIMIT 1
            """,
            chat_id_str,
        )
    else:
        return None

    return int(row["id"]) if row else None


async def get_telegram_chat_id_by_squad_id(conn: asyncpg.Connection, squad_id: int) -> int | None:
    squad_cols = await table_columns(conn, "squads")

    if "telegram_chat_id" in squad_cols:
        row = await conn.fetchrow(
            "SELECT telegram_chat_id FROM squads WHERE id = $1",
            squad_id,
        )
        if not row or row["telegram_chat_id"] is None:
            return None
        return int(row["telegram_chat_id"])

    if "chatters_id" not in squad_cols or not await table_columns(conn, "chatters"):
        return None

    row = await conn.fetchrow(
        """
        SELECT c.telegram_chat_id
        FROM squads AS s
            JOIN chatters AS c ON c.id = s.chatters_id
        WHERE s.id = $1
        """,
        squad_id,
    )
    if not row or row["telegram_chat_id"] is None:
        return None
    return int(row["telegram_chat_id"])


async def create_squad_for_chat(
    conn: asyncpg.Connection,
    chat_id: int,
    name: str,
    tags: str,
    thread_id: int | None = None,
) -> int:
    from logic.squads import db as squads_db
    from logic.squads.models import SquadForm

    squad_cols = await table_columns(conn, "squads")
    if "telegram_chat_id" in squad_cols:
        return await squads_db.create(
            conn,
            SquadForm(
                telegram_chat_id=chat_id,
                telegram_chat_thread_id=thread_id,
                name=name,
                tags=tags,
            ),
        )

    if "chatters_id" not in squad_cols or not await table_columns(conn, "chatters"):
        raise RuntimeError("Unsupported squads schema")

    if await get_squad_id_by_telegram_chat_id(conn, chat_id) is not None:
        raise ValueError("squad_exists")

    chatter_row = await conn.fetchrow(
        """
        INSERT INTO chatters (telegram_chat_id, telegram_chat_thread_id)
        VALUES ($1, $2)
        RETURNING id
        """,
        str(chat_id),
        str(thread_id or ""),
    )
    squad_row = await conn.fetchrow(
        """
        INSERT INTO squads (chatters_id, name, tags)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        chatter_row["id"],
        name,
        tags,
    )
    return int(squad_row["id"])
