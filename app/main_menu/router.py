import logging
from collections import defaultdict
from contextlib import suppress
from datetime import datetime

import pytz
from aiogram import types, F, Router, MagicFilter
from aiogram.enums import ChatType, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.formatting import as_list, as_marked_section, Bold, BlockQuote, as_line

from app.kill_log.shortcuts import edit_ui_with_ocap
from app.main_menu.fsm import SquadFSM
from app.main_menu.misc import main_menu_open, main_menu_ui_open
from app.shortcuts import allow_msg_edit
from core.app_state import AppState
from logic.attendances import db as attendances_db
from logic.attendances.enums import AttendStatus
from logic.attendances.misc import ATTENDANCE_EMOJI
from logic.kill_log.misc import get_game_type
from logic.players import db as players_db
from logic.players.models import PlayerForm
from logic.schedules.misc import DAYS_OF_WEEK
from logic.squads import db as squads_db

router = Router()

NOT_IN_SQUAD_MSG = (
    "Вы не зарегистрированы в отряде %s.\n\n"
    "Введите ваш ник без клан-тега (например, `[TAG]Player` нужно вписать как `Player`) через /reg\n"
    "Должно получиться `/reg Player`"
)

ALREADY_IN_SQUAD_MSG = (
    "Вы уже зарегистрированы в отряде %s.\n\n"
    "Если вы хотите перейти в другой отряд, напишите в личных сообщениях команду `/unreg`."
)

CHECK_MESSAGES = (
    "Проверьте личные сообщения с ботом, он прислал Вам инструкции."
)

ATTENDANCE_STR_MAP = {
    AttendStatus.WILL_ATTEND: "Придут",
    AttendStatus.DOUBTS: "Сомневаются",
    AttendStatus.WILL_NOT_ATTEND: "Не придут",
}


@router.message(CommandStart())
async def start_behavior(message: types.Message):
    match message.chat.type:
        case ChatType.PRIVATE:
            await message.reply(
                    f"Привет, {message.from_user.full_name}.\n"
                    "Чтобы получить килл-лог других отрядов, "
                    "введите простое название (без кавычек и прочих знаков). Например, `!tvt1 re` или `!if re`\n"
                    "Чтобы получить килл-лог за прошлые игры, введите название отряда как выше, но с `<-><кол-во игр>` "
                    "(`-` ни на что не влияет)."
                    "Например, `!tvt1 re 1` - получить за килл-лог отряда RE за позапрошлую игру TVT1, "
                    "`!tvt2 re -2` - за 2 игры до последней игры TVT2, и т.д.\n"
                    "Функционал получения килл-логов за игру пока реализован только для А3\n\n"
                    
                    "Настроить свое расписание в отряде - введите в личку (cюда): /schedule.\n"
                    "Если не работает, проверьте, может ли бот прислать Вам сообщение.\n\n"
                    
                    "Если Вы нашли баг или имеется идея по улучшению, сообщите, пожалуйста, сюда через: /bug. "
                    "Опишите баг как можно подробнее, пожалуйста, чтобы я мог его повторить и починить.\n"
                    "А если интересно, что планируется еще в боте: /road_map\n\n"
                    
                    "ДЛЯ АДМИНОВ/ГЛАВ ОТРЯДОВ:\n"
                    "Бот рассчитан под использование внутри темы группы, хоть и может работать в группе без тем\n"
                    "Для того, чтобы внедрить бота в свою группу, "
                    "просто добавь бота, выдай права админа на удаление сообщений "
                    "и пропиши в нужной теме группы /start_asb .\n"
                    "Не забудь настроить бота через /admin_asb "
                    "(расписание игр, например, или можно подправить тэги или имя отряда), "
                    "после того как добавил и стартанул бота. \n\n"
                )
            return
        case ChatType.SUPERGROUP:
            return


@router.message(Command("start_asb"))
async def start_behavior_asb(message: types.Message, state: FSMContext):
    match message.chat.type:
        case ChatType.PRIVATE:
            await message.reply("Эта команда доступна только для групп.")
            return
        case ChatType.SUPERGROUP:
            try:
                await message.delete()
            except TelegramBadRequest:
                await message.answer(text="Боту нужно выдать админские права удаления сообщений для нормальной работы.")
                return
            squad = await squads_db.get_by_chat(AppState().conn, message.chat.id, message.message_thread_id)

            if not squad or not (squad.telegram_chat_id and squad.telegram_chat_thread_id):
                user = await AppState().bot.get_chat_member(message.chat.id, message.from_user.id)
                if user.status not in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}:
                    await message.reply("Вы не являетесь администратором группы.")
                    return

                # TODO: В FCM можно вписать user_id и сверять его,
                #  дабы никто случайно или специально не вбил рандом инфу.
                last_message = await message.answer(
                    "Регистрация канала в боте.\nВведите название вашего отряда.",
                )
                await state.update_data(registration_message=last_message)
                await state.set_state(SquadFSM.name)
                return
            else:
                await main_menu_open(message, squad)


@router.callback_query(F.data == "main_menu_attendance")
async def main_menu_attendance_callback(callback: CallbackQuery):
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)
    if not squad.ui_message_id:
        await main_menu_ui_open(callback.message, squad)

    player = await players_db.get_by_tg_id(app_state.conn, callback.from_user.id, squad.id)
    if not player:
        await callback.answer(
            NOT_IN_SQUAD_MSG % squad.name,
            cache_time=10
        )
        return

    # TODO получать с учетом расписания игроков
    attendances = await attendances_db.get_list_by_squad_id(app_state.conn, squad.id)
    if not attendances:
        msg_text = "Игр пока не добавили в расписание отряда, либо пока никто не отметился."
        if not (msg_hash := allow_msg_edit(squad.ui_message_hash, msg_text)):
            return
        await squads_db.update(app_state.conn, squad.id, ui_message_hash=msg_hash)

        with suppress(TelegramBadRequest):
            await app_state.bot.edit_message_text(
                **as_line(msg_text).as_kwargs(),
                chat_id=callback.message.chat.id,
                message_id=squad.ui_message_id
            )
        return

    sorted_statuses = AttendStatus.WILL_ATTEND, AttendStatus.DOUBTS, AttendStatus.WILL_NOT_ATTEND
    attendances_grouped = defaultdict(lambda: defaultdict(list))
    schedule_presets = {}
    for i in attendances:
        attendances_grouped[i.schedule_preset.id][i.attend_status].append(i)
        schedule_presets[i.schedule_preset.id] = i.schedule_preset

    content = as_list(
        *[
            as_list(
                as_line(
                    Bold(schedule_presets[sp_id].game_name),
                    f" ({DAYS_OF_WEEK[schedule_presets[sp_id].game_day_of_week]} "
                    f"{schedule_presets[sp_id].game_time.strftime('%H:%M')} по МСК)"
                ),
                as_list(
                    *[
                        as_marked_section(
                            Bold(f"({len(i[attend_status])}) {ATTENDANCE_STR_MAP[attend_status]}:"),
                            *[
                                f"{j.player_name} ({j.comment})".strip() if j.comment else j.player_name
                                for j in i[attend_status]
                            ],
                            marker=f"{ATTENDANCE_EMOJI[attend_status]} "
                        )
                        for attend_status in sorted_statuses if i[attend_status]
                    ],
                    sep="\n"
                ),
                sep=""
            ) for sp_id, i in attendances_grouped.items()
        ],
        BlockQuote(f"Обновлено {datetime.now().strftime("%d.%m %H:%M")}"),
        sep="\n\n"
    )

    msg_html = content.as_html()
    if not (msg_hash := allow_msg_edit(squad.ui_message_hash, msg_html)):
        return
    await squads_db.update(app_state.conn, squad.id, ui_message_hash=msg_hash)

    await app_state.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=squad.ui_message_id,
        **content.as_kwargs()
    )


@router.callback_query(F.data == "main_menu_kill_log")
async def main_menu_kill_log_callback(callback: CallbackQuery):
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)

    current_dt = datetime.now(tz=pytz.timezone("Europe/Moscow"))
    game_time = (current_dt + current_dt.utcoffset())
    await edit_ui_with_ocap(
        squad,
        callback.message,
        f"{get_game_type(current_dt)}"  # TODO: Все равно берет ТЗ из системы. Надо смотреть че на сервере.
    )


@router.callback_query(F.data == "main_menu_schedule_settings")
async def main_menu_schedule_settings_callback(callback: CallbackQuery):
    app_state = AppState()
    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)

    player = await players_db.get_by_tg_id(app_state.conn, callback.from_user.id, squad.id)
    if not player:
        await callback.answer(
            NOT_IN_SQUAD_MSG % squad.name,
            cache_time=10
        )
        return

    try:
        await app_state.bot.send_message(
            chat_id=callback.from_user.id,
            text=f"Вы запросили изменение своего расписания в отряде {squad.name}.\n\n"
            "Чтобы изменить свое расписание в отряде, напишите здесь `/schedule`.\n"
        )
    except TelegramForbiddenError:
        await callback.answer(
            "Перед тем, как бот сможет написать Вам инструкции, "
            "перейдите в личные сообщения с ним и напишите `/start`. "
        )
        return

    await callback.answer(
        CHECK_MESSAGES,
        cache_time=10
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


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("reg"), MagicFilter.len(F.text.split(" ")) > 1)
async def player_register(message: types.Message):
    with suppress(TelegramBadRequest):
        await message.delete()

    app_state = AppState()
    player = await players_db.get_by_tg_id(app_state.conn, message.from_user.id)

    if player:
        squad = await squads_db.get(app_state.conn, player.squad_id)
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text=ALREADY_IN_SQUAD_MSG % squad.name,
        )
        return

    cmd: str
    name: str
    new_name = ""
    cmd, name, *_ = message.text.split(" ")
    squad = await squads_db.get_by_chat(app_state.conn, message.chat.id, message.message_thread_id)
    for tag in squad.tags:
        new_name = name.replace(tag, "")
        if new_name != name:
            break

    await players_db.create(
        app_state.conn,
        PlayerForm(
            name=new_name or name,
            telegram_id=message.from_user.id,
            squad_id=squad.id
        )
    )

    await app_state.bot.send_message(
        chat_id=message.from_user.id,
        text=f"Вы были зарегистрированы как `{name}` в отряде {squad.name}.\n\n"
             "Чтобы отвязать аккаунт от отряда, напишите здесь `/unreg`.\n"
             "О найденных багах напишите в бота `/bug`.\n"
             "Для полной информации по боту, напишите `/start`."
    )


@router.message(Command("unreg"))
async def player_unregister(message: types.Message):
    with suppress(TelegramBadRequest):
        await message.delete()
    app_state = AppState()

    player = await players_db.get_by_tg_id(app_state.conn, message.from_user.id)
    if not player:
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text="Вы не привязаны ни к какому отряду."
        )
        return

    squad = await squads_db.get(app_state.conn, player.squad_id)
    if not squad:
        logging.error(f"Failed to unreg: {message.text=}, {player=}")
        await app_state.bot.send_message(
            chat_id=message.from_user.id,
            text="Произошла ошибка. Повторите команду."
        )
        return

    await players_db.delete(app_state.conn, message.from_user.id)
    await app_state.bot.send_message(
        chat_id=message.from_user.id,
        text=f"Вы были отвязаны от отряда {squad.name}."
    )
