from typing import Any
from datetime import date, datetime, timezone
import hmac

import asyncpg
from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import repository, squad_ops
from .schemas import (
    AttendanceOut,
    AttendanceSummaryOut,
    AttendanceUpdateIn,
    BlockedUserOut,
    DebugUnlockIn,
    DebugUnlockOut,
    GameOut,
    GamesUpdateIn,
    MeOut,
    PlayerOut,
    PrimarySquadIn,
    PlayerNameUpdateIn,
    CreateSquadFromChatIn,
    RegisterPlayerIn,
    SchedulePresetOut,
    SchedulePresetCreateIn,
    SchedulePresetUpdateIn,
    ScheduleUpdateIn,
    SquadFriendOut,
    SquadGameCreateIn,
    SquadMemberOut,
    SquadOut,
    SquadRequestIn,
    SquadRequestOut,
)
from ..core.dependencies import activate_debug_admin, debug_mode_enabled, get_bot, get_db, get_telegram_user
from ..core.debug_token import create_debug_token
from ..core.permissions import SquadPermissionError
from ..core.security import TelegramUser
from ..core.state import state
from logic.squad_requests import db as squad_requests_db
from logic.squad_requests.models import RequestType
from logic.squads.access import is_squad_friend, resolve_squad_access
from logic.squads.chat_lookup import get_telegram_chat_id_by_squad_id
from logic.telegram.debug_context import get_debug_admin_telegram_id, set_debug_admin_telegram_id
from logic.telegram.permissions import is_chat_admin

router = APIRouter(prefix="/api/v1", dependencies=[Depends(activate_debug_admin)])

PERMISSION_STATUS = {
    "access_denied": status.HTTP_403_FORBIDDEN,
    "cannot_remove_admin": status.HTTP_403_FORBIDDEN,
    "squad_blocked": status.HTTP_403_FORBIDDEN,
    "target_not_in_squad": status.HTTP_404_NOT_FOUND,
    "telegram_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "already_friend": status.HTTP_400_BAD_REQUEST,
    "request_pending": status.HTTP_400_BAD_REQUEST,
    "not_blocked": status.HTTP_404_NOT_FOUND,
    "game_has_dependencies": status.HTTP_409_CONFLICT,
}


def player_out(player: dict[str, Any] | None) -> PlayerOut | None:
    return PlayerOut.model_validate(player) if player else None


def build_me_response(me: dict[str, Any], telegram_user: TelegramUser) -> dict[str, Any]:
    return {
        **me,
        "memberships": [player_out(m) for m in me["memberships"]],
        "player": player_out(me["player"]),
        "is_debug_admin": get_debug_admin_telegram_id() == telegram_user.id,
    }


def raise_api_error(exc: Exception) -> None:
    if isinstance(exc, SquadPermissionError):
        raise HTTPException(
            status_code=PERMISSION_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.code,
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


def resolve_squad_id(telegram_user: TelegramUser, squad_id: int | None, me: dict[str, Any]) -> int | None:
    if squad_id is not None:
        return squad_id
    return me.get("context_squad_id") or me.get("primary_squad_id")


def filter_attendance_by_game(items: list[dict[str, Any]], game_id: int | None) -> list[dict[str, Any]]:
    if game_id is None:
        return items
    return [
        item
        for item in items
        if ((item.get("schedule_preset") or {}).get("game") or {}).get("id") == game_id
    ]


async def ensure_preset_in_squad(
    conn: asyncpg.Connection,
    squad_id: int,
    preset_id: int,
) -> None:
    presets = await repository.list_presets_for_squad(conn, squad_id)
    if preset_id not in {preset["id"] for preset in presets}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule preset not found")


async def get_squad_chat_id(conn: asyncpg.Connection, squad_id: int) -> int | None:
    return await get_telegram_chat_id_by_squad_id(conn, squad_id)


async def require_squad_admin(
    conn: asyncpg.Connection,
    bot: Bot,
    squad_id: int,
    telegram_id: int,
) -> None:
    if get_debug_admin_telegram_id() == telegram_id:
        return

    member = await repository.get_player_in_squad(conn, telegram_id, squad_id)
    if not member:
        raise SquadPermissionError("access_denied")

    chat_id = await get_squad_chat_id(conn, squad_id)
    if chat_id is None:
        raise SquadPermissionError("telegram_unavailable")
    if not await is_chat_admin(bot, chat_id, telegram_id):
        raise SquadPermissionError("access_denied")


async def require_squad_member(
    conn: asyncpg.Connection,
    squad_id: int,
    telegram_id: int,
) -> None:
    if get_debug_admin_telegram_id() == telegram_id:
        return

    member = await repository.get_player_in_squad(conn, telegram_id, squad_id)
    if not member:
        raise SquadPermissionError("access_denied")


async def require_squad_member_or_friend(
    conn: asyncpg.Connection,
    bot: Bot,
    squad_id: int,
    telegram_id: int,
) -> None:
    if get_debug_admin_telegram_id() == telegram_id:
        return

    access = await resolve_squad_access(conn, bot, telegram_id, squad_id)
    if access in ("member", "admin", "friend"):
        return
    raise SquadPermissionError("access_denied")


async def require_create_squad_from_chat(bot: Bot, telegram_user: TelegramUser) -> None:
    if telegram_user.launch_chat_id is None:
        raise SquadPermissionError("access_denied")
    if get_debug_admin_telegram_id() == telegram_user.id:
        return
    if not await is_chat_admin(bot, telegram_user.launch_chat_id, telegram_user.id):
        raise SquadPermissionError("access_denied")


async def require_can_set_primary_squad(
    conn: asyncpg.Connection,
    telegram_id: int,
    squad_id: int | None,
) -> None:
    if squad_id is None:
        return
    member = await repository.get_player_in_squad(conn, telegram_id, squad_id)
    if member:
        return
    solo = await repository.get_solo_player(conn, telegram_id)
    if not solo:
        raise ValueError("User is not registered")
    if await squad_requests_db.is_blocked(conn, squad_id, telegram_id):
        raise SquadPermissionError("squad_blocked")
    squad = await repository.get_squad(conn, squad_id)
    if not squad:
        raise ValueError("Squad not found")


async def require_can_create_squad_request(
    conn: asyncpg.Connection,
    telegram_user: TelegramUser,
    squad_id: int,
    request_type: RequestType,
) -> None:
    solo = await repository.get_solo_player(conn, telegram_user.id)
    if not solo:
        raise SquadPermissionError("access_denied")
    if await repository.get_player_in_squad(conn, telegram_user.id, squad_id):
        raise ValueError("already_member")
    if request_type == RequestType.FRIEND and await is_squad_friend(conn, squad_id, solo["id"]):
        raise SquadPermissionError("already_friend")
    if await squad_requests_db.is_blocked(conn, squad_id, telegram_user.id):
        raise SquadPermissionError("squad_blocked")
    if await squad_requests_db.get_pending(conn, squad_id, telegram_user.id):
        raise SquadPermissionError("request_pending")


async def resolve_schedule_context(
    conn: asyncpg.Connection,
    bot: Bot,
    telegram_id: int,
    squad_id: int,
) -> tuple[dict[str, Any], str]:
    access = await resolve_squad_access(conn, bot, telegram_id, squad_id)
    if access == "blocked":
        raise SquadPermissionError("squad_blocked")
    if access in ("member", "admin"):
        player = await repository.get_player_in_squad(conn, telegram_id, squad_id)
        if not player:
            if access == "admin" and get_debug_admin_telegram_id() == telegram_id:
                solo = await repository.get_solo_player(conn, telegram_id)
                if solo:
                    return solo, access
            raise SquadPermissionError("access_denied")
        return player, access
    if access == "friend":
        solo = await repository.get_solo_player(conn, telegram_id)
        if not solo:
            raise SquadPermissionError("access_denied")
        return solo, access
    raise SquadPermissionError("access_denied")


async def resolve_schedule_target(
    conn: asyncpg.Connection,
    bot: Bot,
    caller_id: int,
    squad_id: int,
    target_telegram_id: int | None,
) -> tuple[int, int]:
    if target_telegram_id is None or target_telegram_id == caller_id:
        player, _ = await resolve_schedule_context(conn, bot, caller_id, squad_id)
        return player["id"], squad_id

    await require_squad_admin(conn, bot, squad_id, caller_id)

    target_member = await repository.get_player_in_squad(conn, target_telegram_id, squad_id)
    if target_member:
        return target_member["id"], squad_id

    solo = await repository.get_solo_player(conn, target_telegram_id)
    if solo and await is_squad_friend(conn, squad_id, solo["id"]):
        return solo["id"], squad_id

    raise SquadPermissionError("target_not_in_squad")


async def can_view_summary(
    conn: asyncpg.Connection,
    bot: Bot,
    telegram_id: int,
    squad_id: int,
) -> bool:
    access = await resolve_squad_access(conn, bot, telegram_id, squad_id)
    return access in ("member", "admin", "friend")


@router.get("/me", response_model=MeOut)
async def get_me(
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    me = await repository.get_me(conn, telegram_user)
    me = await squad_ops.enrich_me(conn, bot, me, telegram_user)
    return build_me_response(me, telegram_user)


@router.post("/debug/unlock", response_model=DebugUnlockOut)
async def debug_unlock(
    payload: DebugUnlockIn,
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> dict[str, Any]:
    if not debug_mode_enabled() or state.settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    expected_code = state.settings.WEB_APP_DEBUG_CODE.strip()
    if not hmac.compare_digest(payload.code.strip(), expected_code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_code")

    ttl_seconds = max(1, state.settings.WEB_APP_DEBUG_TOKEN_TTL_SECONDS)
    token, expires_at = create_debug_token(
        telegram_user.id,
        state.settings.API_TOKEN,
        ttl_seconds,
    )
    set_debug_admin_telegram_id(telegram_user.id)
    return {
        "token": token,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc),
    }


@router.post("/debug/lock", status_code=status.HTTP_204_NO_CONTENT)
async def debug_lock() -> None:
    if not debug_mode_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.put("/me/primary-squad", response_model=MeOut)
async def set_primary_squad(
    payload: PrimarySquadIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_can_set_primary_squad(conn, telegram_user.id, payload.squad_id)
        await squad_ops.set_primary_squad_for_user(conn, telegram_user.id, payload.squad_id)
    except Exception as exc:
        raise_api_error(exc)
    me = await repository.get_me(conn, telegram_user)
    me = await squad_ops.enrich_me(conn, bot, me, telegram_user)
    return build_me_response(me, telegram_user)


@router.put("/me/player-name", response_model=MeOut)
async def set_player_name(
    payload: PlayerNameUpdateIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await repository.update_player_name(conn, telegram_user.id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    me = await repository.get_me(conn, telegram_user)
    me = await squad_ops.enrich_me(conn, bot, me, telegram_user)
    return build_me_response(me, telegram_user)


@router.post("/squads/create-from-chat", response_model=SquadOut)
async def create_squad_from_chat(
    payload: CreateSquadFromChatIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_create_squad_from_chat(bot, telegram_user)
        return await squad_ops.create_squad_from_launch_chat(
            conn,
            telegram_user,
            payload.name,
            payload.tags,
        )
    except Exception as exc:
        raise_api_error(exc)


@router.get("/squads", response_model=list[SquadOut])
async def get_squads(
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> list[dict[str, Any]]:
    _ = telegram_user
    return await repository.list_squads(conn)


@router.get("/games", response_model=list[GameOut])
async def get_games(
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> list[dict[str, Any]]:
    _ = telegram_user
    return await repository.list_games(conn)


@router.put("/me/games", response_model=PlayerOut)
async def set_my_games(
    payload: GamesUpdateIn,
    squad_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> dict[str, Any]:
    try:
        return await repository.set_player_games(
            conn,
            telegram_user.id,
            payload.game_ids,
            squad_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/squads/{squad_id}/games", response_model=SquadOut)
async def set_squad_games(
    squad_id: int,
    payload: GamesUpdateIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.set_squad_games_admin(
            conn,
            squad_id,
            payload.game_ids,
            payload.main_game_ids,
        )
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/games", response_model=SquadOut)
async def add_squad_game(
    squad_id: int,
    payload: SquadGameCreateIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.add_squad_game_admin(
            conn,
            squad_id,
            payload.title,
        )
    except Exception as exc:
        raise_api_error(exc)


@router.delete("/squads/{squad_id}/games/{game_id}", response_model=SquadOut)
async def remove_squad_game(
    squad_id: int,
    game_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.remove_squad_game_admin(
            conn,
            squad_id,
            game_id,
        )
    except Exception as exc:
        raise_api_error(exc)


@router.get("/squads/{squad_id}/schedule-presets", response_model=list[SchedulePresetOut])
async def list_schedule_presets(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.list_schedule_presets_admin(conn, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/schedule-presets", response_model=SchedulePresetOut)
async def create_schedule_preset(
    squad_id: int,
    payload: SchedulePresetCreateIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        if payload.recurrence_type == "weekly" and payload.game_day_of_week is None:
            raise ValueError("Weekday is required for weekly events")
        data = payload.model_dump()
        data["title"] = payload.title
        data["game_time"] = f"{payload.game_time}:00"
        return await squad_ops.create_schedule_preset_admin(conn, squad_id, data)
    except Exception as exc:
        raise_api_error(exc)


@router.put("/squads/{squad_id}/schedule-presets/{preset_id}", response_model=SchedulePresetOut)
async def update_schedule_preset(
    squad_id: int,
    preset_id: int,
    payload: SchedulePresetUpdateIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> dict[str, Any]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        data = {key: value for key, value in payload.model_dump().items() if value is not None}
        if payload.game_time is not None:
            data["game_time"] = f"{payload.game_time}:00"
        if payload.title is not None:
            data["title"] = payload.title
        return await squad_ops.update_schedule_preset_admin(conn, squad_id, preset_id, data)
    except Exception as exc:
        raise_api_error(exc)


@router.delete("/squads/{squad_id}/schedule-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_preset(
    squad_id: int,
    preset_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.delete_schedule_preset_admin(conn, squad_id, preset_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/player", response_model=PlayerOut)
async def register_player(
    payload: RegisterPlayerIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> dict[str, Any]:
    try:
        return await repository.register_player(conn, telegram_user, payload.name, payload.squad_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        repository._debug_log(
            "C",
            "router.register_player",
            "unhandled register error",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        raise


@router.delete("/player/solo", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_solo_player(
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> None:
    try:
        await repository.unregister_solo_player(conn, telegram_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/player/{squad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_player(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await squad_ops.leave_squad_self(conn, bot, telegram_user.id, squad_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/squads/{squad_id}/members", response_model=list[SquadMemberOut])
async def get_squad_members(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    try:
        await require_squad_member_or_friend(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.list_squad_members(conn, bot, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.delete("/squads/{squad_id}/members/{telegram_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_squad_member(
    squad_id: int,
    telegram_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.remove_squad_member(conn, bot, squad_id, telegram_id)
    except Exception as exc:
        raise_api_error(exc)


@router.get("/squads/{squad_id}/friends", response_model=list[SquadFriendOut])
async def get_squad_friends(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_ops.list_squad_friends(conn, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.delete("/squads/{squad_id}/friends/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_squad_friend(
    squad_id: int,
    player_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.remove_squad_friend(conn, squad_id, player_id)
    except Exception as exc:
        raise_api_error(exc)


@router.delete("/squads/{squad_id}/friendship", status_code=status.HTTP_204_NO_CONTENT)
async def leave_squad_friendship(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> None:
    try:
        await squad_ops.leave_squad_friendship_self(conn, telegram_user.id, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/requests", response_model=SquadRequestOut)
async def create_squad_request(
    squad_id: int,
    payload: SquadRequestIn,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
) -> dict[str, Any]:
    try:
        request_type = RequestType(payload.request_type)
        await require_can_create_squad_request(conn, telegram_user, squad_id, request_type)
        return await squad_ops.create_squad_request(conn, telegram_user, squad_id, request_type)
    except Exception as exc:
        raise_api_error(exc)


@router.get("/squads/{squad_id}/requests", response_model=list[SquadRequestOut])
async def list_squad_requests(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_requests_db.list_pending_for_squad(conn, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.get("/squads/{squad_id}/blocked", response_model=list[BlockedUserOut])
async def list_blocked_users(
    squad_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        return await squad_requests_db.list_blocked_for_squad(conn, squad_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/requests/{request_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_squad_request(
    squad_id: int,
    request_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.accept_squad_request(conn, squad_id, request_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/requests/{request_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_squad_request(
    squad_id: int,
    request_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.reject_squad_request(conn, squad_id, request_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/requests/{request_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def block_squad_request(
    squad_id: int,
    request_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.block_squad_request(conn, squad_id, request_id)
    except Exception as exc:
        raise_api_error(exc)


@router.post("/squads/{squad_id}/blocked/{telegram_id}/unblock", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_squad_user(
    squad_id: int,
    telegram_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    try:
        await require_squad_admin(conn, bot, squad_id, telegram_user.id)
        await squad_ops.unblock_squad_user(conn, squad_id, telegram_id)
    except Exception as exc:
        raise_api_error(exc)


@router.get("/schedules", response_model=list[SchedulePresetOut])
async def get_schedules(
    squad_id: int | None = Query(default=None),
    target_telegram_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    me = await repository.get_me(conn, telegram_user)
    resolved_squad_id = resolve_squad_id(telegram_user, squad_id, me)
    if resolved_squad_id is None:
        return []
    try:
        player_id, _ = await resolve_schedule_target(
            conn, bot, telegram_user.id, resolved_squad_id, target_telegram_id
        )
        return await repository.list_player_schedule_state(conn, player_id, resolved_squad_id)
    except SquadPermissionError:
        return []


@router.put("/schedules/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_schedule(
    preset_id: int,
    payload: ScheduleUpdateIn,
    squad_id: int | None = Query(default=None),
    target_telegram_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    me = await repository.get_me(conn, telegram_user)
    resolved_squad_id = resolve_squad_id(telegram_user, squad_id, me)
    if resolved_squad_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player is not registered")
    try:
        player_id, _ = await resolve_schedule_target(
            conn, bot, telegram_user.id, resolved_squad_id, target_telegram_id
        )
        await ensure_preset_in_squad(conn, resolved_squad_id, preset_id)
        await repository.set_schedule_default(conn, player_id, preset_id, payload.will_attend_default)
    except Exception as exc:
        raise_api_error(exc)


@router.get("/attendances", response_model=list[AttendanceOut])
async def get_attendances(
    squad_id: int | None = Query(default=None),
    game_id: int | None = Query(default=None),
    week_start: date | None = Query(default=None),
    target_telegram_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    me = await repository.get_me(conn, telegram_user)
    me = await squad_ops.enrich_me(conn, bot, me, telegram_user)
    resolved_squad_id = resolve_squad_id(telegram_user, squad_id, me)
    if resolved_squad_id is None:
        return []
    try:
        player_id, _ = await resolve_schedule_target(
            conn, bot, telegram_user.id, resolved_squad_id, target_telegram_id
        )
        items = await repository.list_player_attendance_state(
            conn, player_id, resolved_squad_id, week=week_start
        )
        return filter_attendance_by_game(items, game_id)
    except SquadPermissionError:
        if (
            me.get("launch_source") == "squad_chat"
            and resolved_squad_id == me.get("launch_squad_id")
            and target_telegram_id is None
        ):
            access = await resolve_squad_access(conn, bot, telegram_user.id, resolved_squad_id)
            if access == "outsider":
                presets = await repository.list_presets_for_squad(
                    conn, resolved_squad_id, current_week_only=True, week=week_start
                )
                items = [
                    {
                        "schedule_preset": preset,
                        "attend_status": None,
                        "weekly_attend_status": None,
                        "comment": "",
                    }
                    for preset in presets
                ]
                return filter_attendance_by_game(items, game_id)
        return []


@router.put("/attendances/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_attendance(
    preset_id: int,
    payload: AttendanceUpdateIn,
    squad_id: int | None = Query(default=None),
    target_telegram_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> None:
    me = await repository.get_me(conn, telegram_user)
    resolved_squad_id = resolve_squad_id(telegram_user, squad_id, me)
    if resolved_squad_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player is not registered")
    try:
        player_id, _ = await resolve_schedule_target(
            conn, bot, telegram_user.id, resolved_squad_id, target_telegram_id
        )
        await ensure_preset_in_squad(conn, resolved_squad_id, preset_id)
        await repository.set_attendance(
            conn, player_id, preset_id, payload.attend_status, payload.comment.strip()
        )
    except Exception as exc:
        raise_api_error(exc)


@router.get("/attendance-summary", response_model=list[AttendanceSummaryOut])
async def get_attendance_summary(
    squad_id: int | None = Query(default=None),
    game_id: int | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    telegram_user: TelegramUser = Depends(get_telegram_user),
    bot: Bot = Depends(get_bot),
) -> list[dict[str, Any]]:
    me = await repository.get_me(conn, telegram_user)
    me = await squad_ops.enrich_me(conn, bot, me, telegram_user)
    resolved_squad_id = resolve_squad_id(telegram_user, squad_id, me)
    if resolved_squad_id is None:
        return []
    try:
        if not await can_view_summary(conn, bot, telegram_user.id, resolved_squad_id):
            return []
        items = await repository.list_attendance_summary(conn, resolved_squad_id)
        return filter_attendance_by_game(items, game_id)
    except SquadPermissionError:
        return []
