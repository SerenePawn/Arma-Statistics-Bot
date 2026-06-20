import asyncpg

from logic.squad_requests.models import RequestStatus, RequestType, SquadRequest


async def is_blocked(conn: asyncpg.Connection, squad_id: int, telegram_id: int) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM squad_requests
        WHERE squad_id = $1 AND telegram_id = $2 AND status = $3
        LIMIT 1
        """,
        squad_id,
        telegram_id,
        RequestStatus.BLOCKED.value,
    )
    return row is not None


async def get_pending(conn: asyncpg.Connection, squad_id: int, telegram_id: int) -> SquadRequest | None:
    row = await conn.fetchrow(
        """
        SELECT id, squad_id, telegram_id, player_id, request_type, status, created_at, resolved_at
        FROM squad_requests
        WHERE squad_id = $1 AND telegram_id = $2 AND status = $3
        LIMIT 1
        """,
        squad_id,
        telegram_id,
        RequestStatus.PENDING.value,
    )
    return SquadRequest.model_validate(dict(row)) if row else None


async def list_pending_for_squad(conn: asyncpg.Connection, squad_id: int) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT
            sr.id,
            sr.squad_id,
            sr.telegram_id,
            sr.player_id,
            sr.request_type,
            sr.status,
            sr.created_at,
            sr.resolved_at,
            p.name AS player_name
        FROM squad_requests AS sr
            JOIN players AS p ON p.id = sr.player_id
        WHERE sr.squad_id = $1 AND sr.status = $2
        ORDER BY sr.created_at
        """,
        squad_id,
        RequestStatus.PENDING.value,
    )
    return [dict(row) for row in rows]


async def list_blocked_for_squad(conn: asyncpg.Connection, squad_id: int) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT
            sr.telegram_id,
            sr.player_id,
            p.name AS player_name,
            COALESCE(sr.resolved_at, sr.created_at) AS blocked_at
        FROM squad_requests AS sr
            JOIN players AS p ON p.id = sr.player_id
        WHERE sr.squad_id = $1 AND sr.status = $2
        ORDER BY blocked_at DESC
        """,
        squad_id,
        RequestStatus.BLOCKED.value,
    )
    return [dict(row) for row in rows]


async def get_by_id(conn: asyncpg.Connection, request_id: int, squad_id: int) -> SquadRequest | None:
    row = await conn.fetchrow(
        """
        SELECT id, squad_id, telegram_id, player_id, request_type, status, created_at, resolved_at
        FROM squad_requests
        WHERE id = $1 AND squad_id = $2
        """,
        request_id,
        squad_id,
    )
    return SquadRequest.model_validate(dict(row)) if row else None


async def create(
    conn: asyncpg.Connection,
    squad_id: int,
    telegram_id: int,
    player_id: int,
    request_type: RequestType,
) -> SquadRequest:
    row = await conn.fetchrow(
        """
        INSERT INTO squad_requests (squad_id, telegram_id, player_id, request_type, status)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, squad_id, telegram_id, player_id, request_type, status, created_at, resolved_at
        """,
        squad_id,
        telegram_id,
        player_id,
        request_type.value,
        RequestStatus.PENDING.value,
    )
    return SquadRequest.model_validate(dict(row))


async def set_status(
    conn: asyncpg.Connection,
    request_id: int,
    status: RequestStatus,
) -> SquadRequest | None:
    row = await conn.fetchrow(
        """
        UPDATE squad_requests
        SET status = $2, resolved_at = NOW()
        WHERE id = $1
        RETURNING id, squad_id, telegram_id, player_id, request_type, status, created_at, resolved_at
        """,
        request_id,
        status.value,
    )
    return SquadRequest.model_validate(dict(row)) if row else None


async def unblock(conn: asyncpg.Connection, squad_id: int, telegram_id: int) -> bool:
    result = await conn.execute(
        """
        UPDATE squad_requests
        SET status = $3, resolved_at = NOW()
        WHERE squad_id = $1 AND telegram_id = $2 AND status = $4
        """,
        squad_id,
        telegram_id,
        RequestStatus.UNBLOCKED.value,
        RequestStatus.BLOCKED.value,
    )
    return result.endswith("1")


async def cancel_pending_for_player(conn: asyncpg.Connection, player_id: int) -> None:
    await conn.execute(
        """
        UPDATE squad_requests
        SET status = $2, resolved_at = NOW()
        WHERE player_id = $1 AND status = $3
        """,
        player_id,
        RequestStatus.REJECTED.value,
        RequestStatus.PENDING.value,
    )
