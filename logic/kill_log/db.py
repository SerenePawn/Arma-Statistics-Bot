from aiosqlite import Connection

from core.db import db
from core.db.db import record_to_model_list
from logic.kill_log.misc import GameType
from logic.kill_log.models import OcapForm, OcapDB, OcapDetail, OcapPlayer, OcapKill


async def create_ocap(conn: Connection, form: OcapForm) -> int:
    try:
        ocap_result = await db.create(
            conn,
            table="ocaps",
            data={
                "filename": form.ocap.filename,
                "length_seconds": form.ocap.length_seconds,
                "game_type": form.ocap.game_type,
                "date_number": form.ocap.date_number,
            },
            commit=False
        )
        ocap_id = ocap_result["last_insert_rowid"]

        for p in form.players:
            await db.create(
                conn,
                table="ocaps_players",
                data={
                    "game_id": p.game_id,
                    "ocap_id": ocap_id,
                    "name": p.name,
                    "group_name": p.group_name,
                    "side": p.side,
                    "dead_at_frame": p.dead_at_frame,
                },
                commit=False
            )

        for k in form.kills:
            await db.create(
                conn,
                table="ocaps_kills",
                data={
                    "ocap_id": ocap_id,
                    "killer_id": k.killer_id,
                    "killed_id": k.killed_id,
                    "killer_vehicle": k.killer_vehicle,
                    "killed_vehicle": k.killed_vehicle,
                    "team_kill": k.team_kill,
                    "frame": k.frame,
                    "weapon": k.weapon,
                    "weapon_is_vehicle": k.weapon_is_vehicle,
                    "distance": k.distance,
                },
                commit=False
            )
    except:
        await conn.rollback()
        raise
    else:
        await conn.commit()
    return ocap_id


async def get_ocaps_by_filenames(conn: Connection, filenames: list[str]) -> list[OcapDB]:
    result = await db.get_by_where(
        conn,
        "ocaps",
        where=f"filename IN ({", ".join("?" for i in filenames)})",
        values=[*filenames]
    )
    if not result:
        return []
    return record_to_model_list(OcapDB, result)


async def get_ocaps_list(conn: Connection) -> list[OcapDB]:
    result = await db.get_list(
        conn,
        "ocaps"
    )
    if not result:
        return []
    return record_to_model_list(OcapDB, result)


async def get_ocap_detail(conn: Connection, game_type: GameType, clan_tag: str, num: int = 0) -> OcapDetail | None:
    ocap_offset = abs(num)
    # Это пиздец. Ебнешься скрипты на sqlite писать. Я будто на чистом си пишу залупу какую-то.
    # Запрос возможных тэгов сквада
    result_found_tags = await conn.execute_fetchall(f"""
        WITH RECURSIVE split(value, str) AS (
            SELECT NULL, (select group_concat(tags) FROM squads WHERE tags LIKE '%{clan_tag}%') || ','
            UNION ALL
            SELECT
                SUBSTR(s.str, 0, INSTR(s.str, ',')),
                SUBSTR(s.str, INSTR(s.str, ',')+1)
            FROM split s
            WHERE s.str != ''
        ) 
        SELECT value AS tag
        FROM split 
        WHERE value IS NOT NULL
            AND TRIM(value, '[]-=+*.') LIKE '{clan_tag}';
    """)  # TODO: убрать из ф-строки инжекты клан-тега. Меня просто так заебали эти скрипты, что ну не могу уже..
    found_tags = [f"name LIKE '{i["tag"]}%'" for i in result_found_tags]
    if not found_tags:
        return None

    # STMTs here
    with_loa_stmt = f"""
        WITH last_ocap_array AS (
            SELECT o.id
            FROM ocaps o
            WHERE o.game_type = '{game_type}'
            ORDER BY o.date_number DESC
            LIMIT 1 OFFSET {ocap_offset}
        )
    """
    with_stmt = f"""
        {with_loa_stmt}, ply_groups AS (
            SELECT op.group_name
            FROM ocaps_players op
            WHERE ({" OR ".join(found_tags)})
                AND ocap_id IN last_ocap_array
            GROUP BY op.group_name
        ), ply_sides AS (
            SELECT op.side
            FROM ocaps_players op
            WHERE ({" OR ".join(found_tags)})
                AND ocap_id IN last_ocap_array
            GROUP BY op.group_name
        )
    """

    # Запрос инфы последнего окапа
    ocap_result = await conn.execute_fetchall(f"""
        {with_loa_stmt}
        SELECT 
          o.*
        FROM ocaps o
        WHERE o.id in last_ocap_array
    """)  # TODO: убрать из ф-строки инжекты клан-тега. Меня просто так заебали эти скрипты, что ну не могу уже..
    if not ocap_result:
        return None
    ocap_meta_data, *_ = ocap_result

    # Запрос киллов из сквада
    result = await conn.execute_fetchall(f"""
        {with_stmt}
        SELECT 
            opk.name, 
            opk.group_name,
            COALESCE(ok.killer_vehicle, ok.weapon) AS weapon, 
            COALESCE(opv.name, ok.killed_vehicle) AS victim_name, 
            ok.killed_vehicle IS NOT NULL AS victim_is_vehicle,
            ok.weapon_is_vehicle,
            ok.team_kill,
            ok.distance
        FROM ocaps o
            LEFT JOIN ocaps_kills ok ON ok.ocap_id = o.id
            LEFT JOIN ocaps_players opk ON opk.ocap_id = o.id AND opk.game_id = ok.killer_id
            LEFT JOIN ocaps_players opv ON opv.ocap_id = o.id AND opv.game_id = ok.killed_id
        WHERE o.id IN last_ocap_array
            AND opk.group_name IN ply_groups
            AND opk.side IN ply_sides
            AND COALESCE(opk.name <> opv.name, true)
        ORDER BY opk.name DESC;
    """)  # TODO: убрать из ф-строки инжекты клан-тега. Меня просто так заебали эти скрипты, что ну не могу уже..
    if not result:
        return None

    # Запрос киллов игроков, найденных выше  # TODO: stmt
    killed_result = await conn.execute_fetchall(f"""
        {with_stmt}
        SELECT 
            opk.name, 
            opk.group_name,
            COALESCE(ok.killer_vehicle, ok.weapon) AS weapon, 
            COALESCE(opv.name, ok.killed_vehicle) AS victim_name, 
            ok.killed_vehicle IS NOT NULL AS victim_is_vehicle,
            ok.weapon_is_vehicle,
            ok.team_kill,
            ok.distance
        FROM ocaps o
            LEFT JOIN ocaps_kills ok ON ok.ocap_id = o.id
            LEFT JOIN ocaps_players opk ON opk.ocap_id = o.id AND opk.game_id = ok.killer_id
            LEFT JOIN ocaps_players opv ON opv.ocap_id = o.id AND opv.game_id = ok.killed_id
        WHERE o.id in last_ocap_array
          and ({" OR ".join([f"victim_name LIKE '{i["tag"]}%'" for i in result_found_tags])});
    """)  # TODO: убрать из ф-строки инжекты клан-тега. Меня просто так заебали эти скрипты, что ну не могу уже..
    if not killed_result:
        return None
    players_killed = {i["victim_name"]: i["name"] for i in killed_result}

    players = {}
    for i in result:
        if i["name"] not in players:
            #
            players[i["name"]] = OcapPlayer(
                name=i["name"],
                group_name=i["group_name"],
                killed_by=players_killed.get(i["name"])
            )

    for i in result:
        players[i["name"]].kills.append(
            OcapKill(
                weapon=i["weapon"],
                weapon_is_vehicle=i["weapon_is_vehicle"],
                victim_name=i["victim_name"],
                victim_is_vehicle=i["victim_is_vehicle"],
                team_kill=i["team_kill"],
                distance=i["distance"],
            )
        )

    return OcapDetail(
        **ocap_meta_data,
        players=players.values(),
    )
