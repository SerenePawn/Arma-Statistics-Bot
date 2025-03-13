import asyncio
import os
import sys
from asyncio import AbstractEventLoop
from collections import defaultdict
from multiprocessing import Process
from pathlib import Path
from time import time

from loguru import logger

from app.attendances.misc import get_attendance_keyboard, get_attendance_text
from core.app_state import AppState
from core.db.db import init
from logic.attendances import db as attendances_db
from logic.kill_log import db as kill_logs_db
from logic.kill_log.misc import OCAP, Player, Vehicle
from logic.kill_log.models import OcapForm, OcapDBForm, OcapPlayerForm, OcapKillForm
from logic.players import db as players_db
from logic.schedules import db as schedules_db
from logic.schedules.models import SchedulePreset


async def send_attendances(app_state: AppState, loop: AbstractEventLoop):
    logger.info("Sending attendances")
    attendances_to_remind = await schedules_db.get_presets_today(app_state.conn)
    logger.debug(f"{attendances_to_remind=}")
    if not attendances_to_remind:
        return

    squads_attendances_today = defaultdict(list[SchedulePreset])
    for attendance in attendances_to_remind:
        squads_attendances_today[attendance.squad_id].append(attendance)

    futures = []

    for squad_id, attendances in squads_attendances_today.items():
        players = await players_db.get_by_squad_id(app_state.conn, squad_id)
        for schedule in attendances:
            for player in players:
                # TODO сделать мапу посещений; оптимизация
                attendance = await attendances_db.get_attendance(app_state.conn, schedule.id, player.id)
                futures.append(asyncio.run_coroutine_threadsafe(
                    app_state.bot.send_message(
                        player.telegram_id,
                        **get_attendance_text(schedule, attendance).as_kwargs(),
                        reply_markup=get_attendance_keyboard(schedule.id, player.id)
                    ),
                    loop
                ))

    for i in futures:
        i.result()


async def old__parse_ocaps(app_state: AppState, *args, **kwargs):
    logger.info("Checking for new OCAPs")
    ocaps_path = app_state.config.OCAPS_PATH
    ocaps = os.listdir(ocaps_path)
    ocaps_filenames = [i.filename for i in await kill_logs_db.get_ocaps_list(app_state.conn)]
    ocaps_to_parse = [i for i in ocaps if i not in ocaps_filenames]
    if ocaps_to_parse:
        logger.info(f"Found new OCAPs ({len(ocaps_to_parse)}): {", ".join(ocaps_to_parse)}! "
                    f"Please, do not kill bot process.")
    else:
        return

    start_time = time()
    processes = []
    for ocap_filename in ocaps_to_parse:
        logger.info(f"Parsing OCAP: '{ocap_filename}'")
        start_iter_time = time()
        ocap = OCAP.from_file(ocaps_path / ocap_filename)
        await kill_logs_db.create_ocap(
            app_state.conn,
            OcapForm(
                ocap=OcapDBForm(
                    filename=ocap_filename,
                    length_seconds=ocap.max_frame,
                    game_type=ocap.game_type,
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
        logger.info(f"Parsed OCAP: '{ocap_filename}' ({round(time() - start_iter_time, 2)}s)")

    logger.info(f"Parsing OCAPs DONE! Total: ({round(time() - start_time, 2)}s)")


async def parse_ocaps(app_state: AppState, *args, **kwargs):
    logger.info("Checking for new OCAPs")
    ocaps_path = app_state.config.OCAPS_PATH
    ocaps = os.listdir(ocaps_path)
    ocaps_filenames = [i.filename for i in await kill_logs_db.get_ocaps_list(app_state.conn)]
    ocaps_to_parse = [i for i in ocaps if i not in ocaps_filenames]
    if ocaps_to_parse:
        logger.info(f"Found new OCAPs ({len(ocaps_to_parse)}): {", ".join(ocaps_to_parse)}! "
                    f"Please, do not kill bot process.")
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
