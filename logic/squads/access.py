from typing import Literal

import asyncpg
from aiogram import Bot

from logic.squad_requests import db as squad_requests_db
from logic.squads.chat_lookup import get_telegram_chat_id_by_squad_id
from logic.squads.friends import parse_friends_ids
from logic.telegram.permissions import is_chat_admin

SquadAccess = Literal["blocked", "outsider", "friend", "member", "admin"]


async def _get_player_in_squad(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int,
) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT id, squad_id, telegram_id, name
        FROM players
        WHERE telegram_id = $1 AND squad_id = $2
        """,
        telegram_id,
        squad_id,
    )
    return dict(row) if row else None


async def _get_solo_player(conn: asyncpg.Connection, telegram_id: int) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT id, squad_id, telegram_id, name
        FROM players
        WHERE telegram_id = $1 AND squad_id IS NULL
        """,
        telegram_id,
    )
    return dict(row) if row else None


async def is_squad_friend(conn: asyncpg.Connection, squad_id: int, player_id: int) -> bool:
    row = await conn.fetchrow("SELECT friends_ids FROM squads WHERE id = $1", squad_id)
    if not row:
        return False
    return player_id in parse_friends_ids(row["friends_ids"])


async def resolve_squad_access(
    conn: asyncpg.Connection,
    bot: Bot | None,
    telegram_id: int,
    squad_id: int,
) -> SquadAccess:
    if await squad_requests_db.is_blocked(conn, squad_id, telegram_id):
        return "blocked"

    member = await _get_player_in_squad(conn, telegram_id, squad_id)
    if member:
        if bot is not None:
            chat_id = await get_telegram_chat_id_by_squad_id(conn, squad_id)
            if chat_id is not None and await is_chat_admin(bot, chat_id, telegram_id):
                return "admin"
        return "member"

    solo_player = await _get_solo_player(conn, telegram_id)
    if solo_player and await is_squad_friend(conn, squad_id, solo_player["id"]):
        return "friend"

    return "outsider"


async def has_registered_admin(
    conn: asyncpg.Connection,
    bot: Bot,
    squad_id: int,
) -> bool:
    chat_id = await get_telegram_chat_id_by_squad_id(conn, squad_id)
    if chat_id is None:
        return False

    rows = await conn.fetch(
        "SELECT telegram_id FROM players WHERE squad_id = $1",
        squad_id,
    )
    for row in rows:
        if await is_chat_admin(bot, chat_id, row["telegram_id"]):
            return True
    return False


def squad_relation_for_ui(access: SquadAccess, has_pending: bool) -> str:
    if access == "blocked":
        return "blocked"
    if access in {"member", "admin"}:
        return "member"
    if access == "friend":
        return "friend"
    if has_pending:
        return "pending"
    return "outsider"
