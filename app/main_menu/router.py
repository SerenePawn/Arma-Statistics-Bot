from contextlib import suppress
from datetime import datetime

import pytz
from aiogram import types, F, Router, MagicFilter
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.kill_log.shortcuts import edit_ui_with_ocap
from app.main_menu.markup import build_group_menu
from core.app_state import AppState
from logic.kill_log.misc import get_game_type
from logic.players import db as players_db
from logic.players.models import PlayerForm
from logic.squads import db as squads_db
from logic.users import db as users_db

router = Router()

ALREADY_IN_SQUAD_MSG = (
    "Вы уже зарегистрированы в отряде %s."
)


@router.message(F.web_app_data)
async def get_data(message: types.Message):
    print(message.web_app_data.data)


@router.message(Command("start_asb"))
async def start_behavior_asb(message: types.Message):
    await AppState().bot.send_message(
        message.chat.id,
        message_thread_id=message.message_thread_id,
        text="Главное меню",
        reply_markup=build_group_menu(message.chat.id),
        protect_content=True,
        disable_notification=True
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("schedule"))
async def schedule_webapp(message: types.Message):
    app_state = AppState()
    squad = await squads_db.get_by_chat_thread_any(app_state.conn, message.chat.id)
    if not squad:
        await message.reply("Отряд для этого чата не найден.")
        return

    await message.reply(
        f"Расписание отряда {squad.name}",
        reply_markup=build_group_menu(message.chat.id),
        protect_content=True,
        disable_notification=True,
    )


@router.callback_query(F.data == "main_menu_kill_log")
async def main_menu_kill_log_callback(callback: CallbackQuery):
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)

    current_dt = datetime.now(tz=pytz.timezone("Europe/Moscow"))
    await edit_ui_with_ocap(
        squad,
        callback.message,
        f"{get_game_type(current_dt)}"
    )


@router.callback_query(F.data == "main_menu_register_player")
async def main_menu_register_player_callback(callback: CallbackQuery, state: FSMContext):
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)

    player = await players_db.get_by_tg_id(app_state.conn, callback.from_user.id, squad.id)
    if player:
        await callback.answer(
            ALREADY_IN_SQUAD_MSG % squad.name,
            cache_time=10
        )
        return

    await callback.answer(
        f"Как связать телеграм с ником армы в отряде {squad.name}:\n"
        "Введите ваш ник без клан-тега (например, `[TAG]Player` нужно вписать как `Player`) через /reg\n"
        "Должно получиться `/reg Player`\n",
        show_alert=True,
        cache_time=10
    )


def strip_squad_tags(name: str, tags: list[str]) -> str:
    for tag in tags:
        stripped = name.replace(tag, "")
        if stripped != name:
            return stripped
    return name


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("reg"), MagicFilter.len(F.text.split(" ")) > 1)
async def player_register(message: types.Message):
    with suppress(TelegramBadRequest):
        await message.delete()

    app_state = AppState()
    _, name, *_ = message.text.split(" ")
    squad = await squads_db.get_by_chat_thread_any(app_state.conn, message.chat.id)
    if not squad:
        return

    existing = await players_db.get_by_tg_id(app_state.conn, message.from_user.id, squad.id)
    if existing:
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text=ALREADY_IN_SQUAD_MSG % squad.name,
        )
        return

    clean_name = strip_squad_tags(name, squad.tags) or name
    await players_db.upsert_in_squad(
        app_state.conn,
        PlayerForm(
            name=clean_name,
            telegram_id=message.from_user.id,
            telegram_tag=message.from_user.username or "",
            squad_id=squad.id,
        ),
    )

    memberships = await players_db.get_all_by_tg_id(app_state.conn, message.from_user.id)
    prefs = await users_db.get_preferences(app_state.conn, message.from_user.id)
    if len(memberships) == 1 or not prefs or prefs.primary_squad_id is None:
        await users_db.set_primary_squad(app_state.conn, message.from_user.id, squad.id)

    with suppress(TelegramForbiddenError):
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text=f"Вы были зарегистрированы как `{clean_name}` в отряде {squad.name}.\n\n"
                 "Чтобы отвязать аккаунт от этого отряда, напишите `/unreg` в чате отряда.\n"
                 "О найденных багах напишите в бота `/bug`.\n"
                 "Для полной информации по боту, напишите `/start`."
        )


@router.message(Command("unreg"))
async def player_unregister(message: types.Message):
    with suppress(TelegramBadRequest):
        await message.delete()
    app_state = AppState()

    if message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        squad = await squads_db.get_by_chat_thread_any(app_state.conn, message.chat.id)
        if not squad:
            await app_state.bot.send_message(
                chat_id=message.from_user.id,
                text="Не удалось определить отряд для этого чата.",
            )
            return

        player = await players_db.get_by_tg_id(app_state.conn, message.from_user.id, squad.id)
        if not player:
            await app_state.bot.send_message(
                chat_id=message.from_user.id,
                text=f"Вы не зарегистрированы в отряде {squad.name}.",
            )
            return

        await players_db.delete_from_squad(app_state.conn, message.from_user.id, squad.id)
        await users_db.reassign_primary_after_leave(app_state.conn, message.from_user.id, squad.id)
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text=f"Вы были отвязаны от отряда {squad.name}.",
        )
        return

    memberships = await players_db.get_all_by_tg_id(app_state.conn, message.from_user.id)
    if not memberships:
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text="Вы не привязаны ни к какому отряду.",
        )
        return

    squad_names = []
    for membership in memberships:
        squad = await squads_db.get(app_state.conn, membership.squad_id)
        if squad:
            squad_names.append(squad.name)

    await app_state.bot.send_message(
        chat_id=message.from_user.id,
        text=(
            "Чтобы покинуть отряд, используйте `/unreg` в чате нужного отряда.\n\n"
            f"Ваши отряды: {', '.join(squad_names) if squad_names else 'нет'}."
        ),
    )
