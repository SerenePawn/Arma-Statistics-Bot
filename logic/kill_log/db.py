import asyncpg

from core.db import db
from core.db.db import record_to_model_list
from logic.kill_log.misc import GameType
from logic.kill_log.models import OcapForm, OcapDB, OcapDetail, OcapPlayer, OcapKill


async def create_ocap(conn: asyncpg.Connection, form: OcapForm) -> int:
    async with conn.transaction():
        ocap_result = await db.create(
            conn,
            table="ocaps",
            data={
                "filename": form.ocap.filename,
                "length_seconds": form.ocap.length_seconds,
                "game_type": form.ocap.game_type,
                "date_number": form.ocap.date_number,
            },
        )
        ocap_id = ocap_result["id"]

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
            )
    return ocap_id


async def get_ocaps_by_filenames(conn: asyncpg.Connection, filenames: list[str]) -> list[OcapDB]:
    if not filenames:
        return []
    result = await db.get_by_where(
        conn,
        "ocaps",
        where=f"filename IN ({', '.join([f'${i + 1}' for i in range(len(filenames))])})",
        values=[*filenames],
        return_rows=True,
    )
    if not result:
        return []
    return record_to_model_list(OcapDB, result)


async def get_ocaps_list(conn: asyncpg.Connection) -> list[OcapDB]:
    result = await db.get_list(
        conn,
        "ocaps"
    )
    if not result:
        return []
    return record_to_model_list(OcapDB, result)


async def get_ocap_detail(conn: asyncpg.Connection, game_type: GameType, clan_tag: str, num: int = 0) -> OcapDetail | None:
    ocap_offset = abs(num)
    result_found_tags = await db.get_raw(
        conn,
        """
        SELECT tags
        FROM squads
        WHERE tags ILIKE $1
        """,
        [f"%{clan_tag}%"],
    )
    normalized = clan_tag.strip("[]-=+*.").lower()
    found_tags = []
    for row in result_found_tags:
        for tag in (row["tags"] or "").split(","):
            if tag.strip("[]-=+*.").lower() == normalized:
                found_tags.append(tag)
    if not found_tags:
        return None

    ocap_result = await db.get_raw(
        conn,
        """
        SELECT o.*
        FROM ocaps o
        WHERE o.game_type = $1
        ORDER BY o.date_number DESC
        LIMIT 1 OFFSET $2
        """,
        [game_type, ocap_offset],
    )
    if not ocap_result:
        return None
    ocap_meta_data, *_ = ocap_result
    ocap_id = ocap_meta_data["id"]

    like_filters = " OR ".join([f"op.name ILIKE ${i + 2}" for i in range(len(found_tags))])
    like_values = [f"{tag}%" for tag in found_tags]
    players_scope = await db.get_raw(
        conn,
        f"""
        SELECT DISTINCT op.name, op.group_name, op.side
        FROM ocaps_players op
        WHERE op.ocap_id = $1 AND ({like_filters})
        """,
        [ocap_id, *like_values],
    )
    if not players_scope:
        return OcapDetail(**ocap_meta_data, players=[])

    groups = {row["group_name"] for row in players_scope}
    sides = {row["side"] for row in players_scope}
    group_filters = " OR ".join([f"opk.group_name = ${i + 2}" for i in range(len(groups))])
    side_filters = " OR ".join([f"opk.side = ${i + 2 + len(groups)}" for i in range(len(sides))])

    result = await db.get_raw(
        conn,
        f"""
        SELECT 
            opk.name, 
            opk.group_name,
            COALESCE(ok.killer_vehicle, ok.weapon) AS weapon, 
            COALESCE(opv.name, ok.killed_vehicle) AS victim_name, 
            ok.killed_vehicle IS NOT NULL AS victim_is_vehicle,
            ok.weapon_is_vehicle,
            ok.team_kill,
            ok.distance
        FROM ocaps_kills ok
            LEFT JOIN ocaps o ON ok.ocap_id = o.id
            LEFT JOIN ocaps_players opk ON opk.ocap_id = o.id AND opk.game_id = ok.killer_id
            LEFT JOIN ocaps_players opv ON opv.ocap_id = o.id AND opv.game_id = ok.killed_id
        WHERE o.id = $1
            AND ({group_filters})
            AND ({side_filters})
            AND COALESCE(opk.name <> opv.name, true)
        ORDER BY opk.name DESC;
    """,
        [ocap_id, *groups, *sides],
    )
    if not result:
        result = []

    victim_filters = " OR ".join([f"COALESCE(opv.name, ok.killed_vehicle) ILIKE ${i + 2}" for i in range(len(found_tags))])
    killed_result = await db.get_raw(
        conn,
        f"""
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
        WHERE o.id = $1 AND ({victim_filters});
    """,
        [ocap_id, *like_values],
    )
    if not killed_result:
        killed_result = []
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
