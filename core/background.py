import asyncio
import os
import sys
from asyncio import AbstractEventLoop
from collections import defaultdict
from contextlib import suppress
from multiprocessing import Process
from pathlib import Path
from time import time

import requests
from aiogram.exceptions import TelegramForbiddenError
from loguru import logger

from app.attendances.misc import get_attendance_keyboard, get_attendance_text
from core.app_state import AppState
from core.consts import OCAPS_URL, OCAP_URL
from core.db.db import init
from logic.attendances import db as attendances_db
from logic.attendances.enums import AttendStatus
from logic.kill_log import db as kill_logs_db
from logic.kill_log.misc import OCAP, Player, Vehicle
from logic.kill_log.models import OcapForm, OcapDBForm, OcapPlayerForm, OcapKillForm
from logic.players import db as players_db
from logic.schedules import db as schedules_db
from logic.schedules.models import SchedulePreset


async def send_attendances(app_state: AppState, loop: AbstractEventLoop):
    logger.info("Sending attendances")
    attendances_to_remind = await schedules_db.get_presets(app_state.conn)
    logger.debug(f"{attendances_to_remind=}")
    if not attendances_to_remind:
        return

    squads_attendances_today = defaultdict(list[SchedulePreset])
    for attendance in attendances_to_remind:
        squads_attendances_today[attendance.squad_id].append(attendance)

    tasks = []

    for squad_id, attendances in squads_attendances_today.items():
        players = await players_db.get_by_squad_id(app_state.conn, squad_id)
        for schedule_preset in attendances:
            for player in players:
                # TODO сделать мапу посещений; оптимизация
                attendance = await attendances_db.get_attendance(app_state.conn, schedule_preset.id, player.id)
                schedule = await schedules_db.get_schedule_by_player(app_state.conn, player.id, schedule_preset.id)

                if not (attendance or schedule) or (
                        (schedule and schedule.will_attend_default is True)
                        and (
                            not attendance
                            or attendance.attend_status in {AttendStatus.WILL_ATTEND, AttendStatus.DOUBTS}
                        )
                ):
                    logger.debug(f"[ATD] Sending [{schedule_preset.game_name}] "
                                 f"to [{player.name}] (tg_id={player.telegram_id})")
                    tasks.append(
                        app_state.bot.send_message(
                            player.telegram_id,
                            **get_attendance_text(schedule_preset, schedule, attendance).as_kwargs(),
                            reply_markup=get_attendance_keyboard(schedule_preset.id, player.id)
                        )
                    )

    logger.debug(f"[ATD] Sending {len(tasks)}")
    results = []
    for i in tasks:
        with suppress(TelegramForbiddenError):
            r = asyncio.run_coroutine_threadsafe(i, loop)
            results.append(r)
    logger.debug(f"[ATD] Sent {len(results)}")


async def download_ocaps(app_state: AppState) -> list[str]:
    ocaps = os.listdir(app_state.config.OCAPS_PATH)
    response = requests.get(OCAPS_URL)
    downloaded_ocaps = [i for i in response.json() if i["filename"] not in ocaps]

    for i in downloaded_ocaps:
        response_ocap = requests.get(OCAP_URL % i["filename"])
        with open(f"{app_state.config.OCAPS_PATH}/{i["filename"]}", "w", encoding="utf-8") as fd:
            fd.write(response_ocap.text)

    return downloaded_ocaps


async def parse_ocaps(app_state: AppState, *args, **kwargs):
    logger.info("Checking for new OCAPs")

    # TODO: Пока не на сервере с окапами, будет качать окапы. Удалить после размещения на сервере с окапами.
    downloaded = await download_ocaps(app_state)
    if not downloaded:
        return

    ocaps_path = app_state.config.OCAPS_PATH
    ocaps = os.listdir(ocaps_path)
    ocaps_filenames = [i.filename for i in await kill_logs_db.get_ocaps_list(app_state.conn)]
    ocaps_to_parse = [i for i in ocaps if i not in ocaps_filenames]
    if ocaps_to_parse:
        logger.info(f"Found new OCAPs ({len(ocaps_to_parse)}): {", ".join(ocaps_to_parse)}!")
    else:
        return

    start_time = time()
    processes = []

    for ocap_filename in ocaps_to_parse:
        processes.append(
            Process(target=run_coro, args=(__parse_ocap, ocaps_path, ocap_filename))
        )
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=30)

    logger.info(f"Parsing OCAPs DONE! Total: ({round(time() - start_time, 2)}s)")


def run_coro(coro, *args, **kwargs):
    asyncio.run(coro(*args, **kwargs))


async def __parse_ocap(ocaps_path: Path, ocap_filename: str):
    ocap = OCAP.from_file(ocaps_path / ocap_filename)
    app_state = AppState()
    app_state.conn = await init(app_state.config)
    await kill_logs_db.create_ocap(
        app_state.conn,
        OcapForm(
            ocap=OcapDBForm(
                filename=ocap_filename,
                length_seconds=ocap.max_frame,
                game_type=ocap.game_type,
                date_number=int(ocap_filename[:17].replace("_", ""))
            ),
            players=[OcapPlayerForm(
                game_id=p.id,
                name=p.name,
                group_name=p.group,
                side=p.side,
                dead_at_frame=len(p.positions),
            ) for p in ocap.players.values()],
            kills=[OcapKillForm(
                killer_id=e.killer.id,
                killed_id=e.killed.id if isinstance(e.killed, Player) else None,
                killer_vehicle=e.killer_vehicle.name if e.killer_vehicle else None,
                killed_vehicle=e.killed.name if isinstance(e.killed, Vehicle) else None,
                team_kill=(
                        (e.killer.side if e.killer else None) == e.killed.side
                ) if isinstance(e.killed, Player) else False,
                frame=e.frame,
                weapon=e.weapon,
                weapon_is_vehicle=bool(e.killer_vehicle),
                distance=e.distance,
            ) for e in ocap.events],
        )
    )
    await app_state.conn.close()
    sys.exit(0)
