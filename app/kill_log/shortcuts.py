from collections import defaultdict
from contextlib import suppress
from datetime import datetime

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from aiogram.utils.formatting import as_list, Bold, as_line, BlockQuote

from app.main_menu.misc import main_menu_ui_open
from app.shortcuts import allow_msg_edit
from core.app_state import AppState
from logic.kill_log import db as kill_log_db
from logic.kill_log.models import OcapPlayer
from logic.squads import db as squads_db
from logic.squads.models import Squad

TG_TAB = " " * 4


async def edit_ui_with_ocap(squad: Squad, message: Message, full_command: str):
    """
    Меняет UI message в канале отряда, открывая инфу по ОКАПу.
    :param squad:
    :param message: Принимает как msg обычный, так и с колбека. Учитывать мультифункциональность при изменении логики.
    :param full_command: Из-за параметра выше, нужно отдельно подать сюда строку с командой для парсинга.
    :return:
    """
    app_state = AppState()
    if not squad:
        return
    if not squad.ui_message_id:
        await main_menu_ui_open(message, squad)

    cmd, *args = full_command.replace("!", "").split(" ")
    clan_tag = None
    offset = 0
    match len(args):
        case 1:
            value = args[0]
            value = value.strip("-")
            if value.isnumeric():
                offset = int(value)
            else:
                clan_tag = value
        case 2:
            clan_tag, offset = args
            if not offset.isnumeric():
                offset = "0"
            offset = int(offset.strip("-"))
    if clan_tag is None:
        clan_tag = squad.tags[0].strip("[].-=+*")

    ocap_data = await kill_log_db.get_ocap_detail(app_state.conn, cmd, clan_tag, offset)
    if not ocap_data:
        msg_text = "ОКАП/клан-тэг/убийства указанного отряда в нем не найдены."
        if not (msg_hash := allow_msg_edit(squad.ui_message_hash, msg_text)):
            return
        await squads_db.update(app_state.conn, squad.id, ui_message_hash=msg_hash)

        with suppress(TelegramBadRequest):
            await app_state.bot.edit_message_text(
                **as_line(msg_text).as_kwargs(),
                chat_id=message.chat.id,
                message_id=squad.ui_message_id,
            )
        return

    kills_grouped: defaultdict[str, list[OcapPlayer]] = defaultdict(list)
    for i in ocap_data.players:
        kills_grouped[i.group_name].append(i)

    plys_killed = len([
        p for p in ocap_data.players
        for k in p.kills if k.victim_is_vehicle is False and not k.team_kill
    ])
    mates_killed = len([
        p for p in ocap_data.players
        for k in p.kills if k.victim_is_vehicle is False and k.team_kill
    ])
    vehicles_killed = len([
        p for p in ocap_data.players
        for k in p.kills if k.victim_is_vehicle is True
    ])
    content = as_list(
        as_line(Bold(ocap_data.game_type.upper()), ocap_data.filename.split(".")[0], sep=" — "),
            as_list(
                as_line(f"☠️ Убито противников отрядом: {plys_killed}"),
                as_line(f"🙉️ Убито своих отрядом: {mates_killed}"),
                as_line(f"💥 Уничтожено техники отрядом: {vehicles_killed}"),
                sep=""
            ),
        *[  # groups iterator
            as_list(
                as_line("⭐️ ", Bold(group), ":"),
                *[
                    as_list(
                        as_line(
                            "🪖️ ",
                            Bold(player.name),
                            " убил ",
                            len([i for i in player.kills if not i.victim_is_vehicle]),
                            f" (убит {player.killed_by})" if player.killed_by else "",
                            ":"
                        ),
                        *[
                            as_line(
                                kill.weapon + " " if kill.weapon else "",
                                f"[{kill.distance}м]" if kill.distance else "",
                                " 🙉 "
                                if kill.team_kill else " 💥 "
                                if kill.victim_is_vehicle else " ☠️ ",
                                kill.victim_name
                            )
                            for kill in player.kills
                        ],
                        sep=f"{TG_TAB*2}"
                    )
                    for player in players
                ],
                sep=f"{TG_TAB}"
            )
            for group, players in kills_grouped.items()
        ],
        BlockQuote(f"Обновлено {datetime.now().strftime("%d.%m %H:%M")}"),
        sep="\n"
    )

    msg_html = content.as_html()
    if not (msg_hash := allow_msg_edit(squad.ui_message_hash, msg_html)):
        return
    await squads_db.update(app_state.conn, squad.id, ui_message_hash=msg_hash)

    with suppress(TelegramBadRequest):
        await app_state.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=squad.ui_message_id,
            **content.as_kwargs()
        )