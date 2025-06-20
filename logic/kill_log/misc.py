import json
import threading
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, time
from enum import StrEnum
from pathlib import Path
from queue import Queue, Empty
from typing import Any

from pydantic import BaseModel, Field, model_validator, field_validator

from core.app_state import AppState

WEAPON_RENAMED = {
    "РПГ-26 (отстрелянный)": "РПГ-26",
    "РШГ-2 (отстрелянный)": "РШГ-2",
    "M136 HEDP (used)": "M136 (HEDP)",
    "M136 HEAT (used)": "M136 (HEAT)",
    "M136 HP (used)": "M136 (HP)",
    "M72A7 (used)": "M72A7",
    "NLAW (Used)": "NLAW",
    "Panzerfaust 3 (Used)": "Panzerfaust 3",
    "[CUP] Mk16 SCAR-L STD (Рукоятка) [Black]": "[CUP] Mk16 SCAR-L",
    "[CUP] Mk16 SCAR-L CQC (EGLM) [Woodland]": "[CUP] Mk16 SCAR-L",
    "[CUP] Mk16 SCAR-L STD (EGLM) [Black]": "[CUP] Mk16 SCAR-L",
    "[CUP] Mk16 SCAR-L STD (EGLM) [Desert]": "[CUP] Mk16 SCAR-L",
    "[CUP] Mk16 SCAR-L STD [Desert]": "[CUP] Mk16 SCAR-L",
    "SR-25 Carbine [Woodland]": "SR-25 Carbine",
    "M249 PIP Long (RIS/Lightweight)": "M249 PIP Long",
    "M249 PIP Short (RIS/SAVIT stock)": "M249 PIP Short",
    "M4A1 Block II (AFG/SOPMOD Stock)": "M4A1 Block II",
    "M4A1 Block II Woodland (SOPMOD stock)": "M4A1 Block II",
    "[Alpha AK] АК-104 (Zenitco) [Woodland]": "АК-74М",
    "[Alpha AK] АК-105 (Zenitco) [Woodland]": "АК-74М",
    "[Alpha AK] АК-74М (Zenitco) [Black]": "АК-74М",
    "[Alpha AK] АК-74М (Zenitco) [Winter]": "АК-74М",
    "[Tier 1] MCX Virtus (.300BLK)[Black]": "MCX Virtus",
}


class GameType(StrEnum):
    LTVT = "ltvt"
    TVT1 = "tvt1"
    TVT2 = "tvt2"
    IF = "if"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    UNIT = "unit"
    VEHICLE = "vehicle"


class VehicleType(StrEnum):
    TRUCK = "truck"
    CAR = "car"
    HELICOPTER = "heli"
    APC = "apc"
    SEA = "sea"
    PARACHUTE = "parachute"
    PLANE = "plane"
    TANK = "tank"
    STATIC_MORTAR = "static-mortar"
    STATIC_WEAPON = "static-weapon"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    KILL = "killed"


class Coordinates(BaseModel):
    # frames_fired: list = Field(alias="framesFired")
    x: int
    y: int

    @model_validator(mode="before")
    @classmethod
    def from_coords_list(cls, data: Any) -> dict:
        return dict(
            zip(
                vars(cls)["__annotations__"], [round(i) for i in data]
            )
        )

    @property
    def as_str(self) -> tuple[str, str]:
        return str(self.x), str(self.y)


class Position(BaseModel):
    # frame - это разница айдишника внутри списка и старт фрейма у игрока.
    coordinates: Coordinates
    azimuth: int

    @model_validator(mode="before")
    @classmethod
    def from_pos_list(cls, data: Any) -> dict:
        return dict(
            zip(
                vars(cls)["__annotations__"], data
            )
        )


class PlayerPosition(BaseModel):
    coordinates: Coordinates
    azimuth: int
    dump_data_first: int  # Поля, которые хорошо бы вообще не добавлять. Только для корректной валидации модели.
    dump_data_second: int  # Поля, которые хорошо бы вообще не добавлять. Только для корректной валидации модели.
    player_name: str

    @model_validator(mode="before")
    @classmethod
    def from_pos_list(cls, data: Any) -> dict:
        return dict(
            zip(
                vars(cls)["__annotations__"], data
            )
        )


class Vehicle(BaseModel):
    id: int
    name: str
    entity_type: EntityType = Field(alias="type")
    vehicle_type: VehicleType | None = Field(None, alias="class")
    start_frame: int = Field(alias="startFrameNum")
    positions: tuple[Position, ...]

    @classmethod
    def map_from_ocap(cls, data: dict) -> dict[int, "Vehicle"]:
        # map[id: player]
        vehicles = [
            cls(**entity) for entity in data["entities"]
            if entity.get("type") == EntityType.VEHICLE and entity.get("class") != VehicleType.PARACHUTE
        ]
        return {p.id: p for p in vehicles}

    @classmethod
    def map_from_ocap_queued(cls, data: dict, queue: Queue) -> None:
        # map[id: player]
        vehicles = [
            cls(**entity) for entity in data["entities"]
            if entity.get("type") == EntityType.VEHICLE and entity.get("class") != VehicleType.PARACHUTE
        ]
        queue.put_nowait({"vehicles": {p.id: p for p in vehicles}})


class Player(BaseModel):
    id: int
    group: str
    name: str
    side: str
    is_player: bool = Field(alias="isPlayer")
    entity_type: EntityType = Field(alias="type")
    start_frame: int = Field(alias="startFrameNum")
    positions: tuple[PlayerPosition, ...]

    @classmethod
    def map_from_ocap(cls, data: dict) -> dict[int, "Player"]:
        # map[id: player]
        players = [
            cls(**entity)
            for entity in data["entities"]
            if entity.get("isPlayer", None) is not None
        ]
        return {p.id: p for p in players}

    @classmethod
    def map_from_ocap_queued(cls, data: dict, queue: Queue) -> None:
        # map[id: player]
        players = [
            cls(**entity)
            for entity in data["entities"]
            if entity.get("isPlayer", None) is not None
        ]
        queue.put_nowait({"players": {p.id: p for p in players}})


class KillFrag(BaseModel):
    killer: int | None = None
    weapon: str | None = None

    @model_validator(mode="before")
    @classmethod
    def from_frag_list(cls, data: list[int, str]) -> dict:
        fields_to_values = dict(
            zip(
                vars(cls)["__annotations__"], data
            )
        )
        killer = fields_to_values.get("killer")
        if killer and killer == "null":
            fields_to_values["killer"] = None
        return fields_to_values


class KillEventRaw(BaseModel):
    frame: int
    event_type: EventType
    killed: int
    frag: KillFrag | None = None
    distance: int

    @classmethod
    def ocap_constructor(cls, data: list[Any]) -> "KillEventRaw":
        fields_to_values = dict(
            zip(
                vars(cls)["__annotations__"], data
            )
        )
        return cls(**fields_to_values)

    @classmethod
    def list_from_ocap(cls, data: dict) -> list["KillEventRaw"]:
        events = [
            cls.ocap_constructor(event)
            for event in data["events"] if event[1] == EventType.KILL
        ]

        return events

    @classmethod
    def list_from_ocap_queued(cls, data: dict, queue: Queue) -> None:
        events = [
            cls.ocap_constructor(event)
            for event in data["events"] if event[1] == EventType.KILL
        ]
        queue.put_nowait({"events": events})


class KillEvent(BaseModel):
    frame: int
    event_type: EventType
    killed: Player | Vehicle
    killer: Player
    killer_vehicle: Vehicle | None = None
    killer_vehicle_crew: list[int] = []
    weapon: str = ""
    distance: int

    def __str__(self):
        weapon = self.killer_vehicle.name if self.killer_vehicle else self.weapon or ""
        return (f"{self.killer.name} убил {self.killed.name} "
                f"{"при помощи `%s`" % weapon if weapon else ""} "
                f"{"(%dм)" % self.distance if self.distance > 0 else ""}")

    @field_validator("weapon", mode="after")
    @classmethod
    def correct_weapons_rename(cls, v: str) -> str:
        result = WEAPON_RENAMED.get(v, v)
        return result.strip()
    @classmethod
    def map_from_ocap(
            cls,
            players: dict[int, Player],
            vehicles: dict[int, Vehicle],
            raw_kills: list[KillEventRaw]
    ) -> list["KillEvent"]:
        return [
            cls(
                frame=event.frame,
                event_type=event.event_type,
                killed=(players | vehicles)[event.killed],
                killer=players[event.frag.killer],
                weapon=event.frag.weapon or "unknown",
                distance=event.distance,
            ) for event in raw_kills
            if (players | vehicles).get(event.killed) and players.get(event.frag.killer)
        ]


class OCAP(BaseModel):
    players: dict[int, Player] | None = None
    vehicles: dict[int, Vehicle] | None = None
    events: list[KillEvent] | None = None
    positions: Any | None = None
    game_type: GameType
    max_frame: int

    @classmethod
    def from_file(cls, path: Path) -> "OCAP":
        with path.open("r", encoding="UTF-8") as fd:
            data = json.load(fd)

        queue = Queue()

        players_thread = threading.Thread(target=Player.map_from_ocap_queued, args=(data, queue), daemon=True)
        players_thread.start()
        vehicles_thread = threading.Thread(target=Vehicle.map_from_ocap_queued, args=(data, queue), daemon=True)
        vehicles_thread.start()
        events_thread = threading.Thread(target=KillEventRaw.list_from_ocap_queued, args=(data, queue), daemon=True)
        events_thread.start()

        players_thread.join()
        vehicles_thread.join()
        events_thread.join()

        thread_1, thread_2, thread_3 = {}, {}, {}
        with suppress(Empty):
            thread_1 = queue.get_nowait()
        with suppress(Empty):
            thread_2 = queue.get_nowait()
        with suppress(Empty):
            thread_3 = queue.get_nowait()

        threads_data = thread_1 | thread_2 | thread_3
        players = threads_data.get("players", {})
        vehicles = threads_data.get("vehicles", {})
        events = threads_data.get("events", {})

        events = KillEvent.map_from_ocap(players, vehicles, events)

        positions = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(list[int])
            )
        )
        for i in (players | vehicles).values():
            for frame, pos in enumerate(i.positions):
                positions[i.entity_type][frame + i.start_frame][
                    (pos.coordinates.x, pos.coordinates.y)
                ].append(i.id)

        ocap = cls(
            players=players,
            vehicles=vehicles,
            events=events,
            positions=positions,
            max_frame=len(positions[EntityType.UNIT]) - 1,  # -1, т.к. отсчет кадров идет с нуля, длину считает с 1.
            game_type=get_game_type_from_file(path)
        )

        # Заполнение ника, если игрок вылетел и стал ботом.
        for p in ocap.players.values():
            p: Player
            if not p.is_player and p.positions:
                for pos in p.positions:
                    if pos.player_name and p.name != pos.player_name:
                        p.name = f"{pos.player_name} [AI]"
                        break

        # Заполнение ТС, на котором был убийца во время фрага.
        for e in ocap.events:
            killer_vehicle_id = parse_player_vehicle_id(ocap, e.killer.id, e.frame)
            if killer_vehicle_id:
                e.killer_vehicle = vehicles[killer_vehicle_id]
                # TODO Тут должен писаться экипаж, чтобы фраг считался всему экипажу, а не только стрелку.
                #  Но это блять какая-то жопорвань, которая основывается и так на костыле поиска чья это блять техника
                # e.killer_vehicle_crew.append(e.killer.id)

                # killer_pos = e.killer.positions[e.frame].coordinates
                # print('>>>>', positions[EntityType.UNIT][e.frame][(killer_pos.x, killer_pos.y)])
                # e.killer_vehicle_crew.extend(
                #     positions[EntityType.UNIT][e.frame][(killer_pos.x, killer_pos.y)]
                # )
                # print('!>>>', parse_players_in_vehicle(ocap, e.killer_vehicle.id, e.frame))

        return ocap


def parse_players_in_vehicle(
        ocap: OCAP,
        vehicle_id: int,
        frame: int,
) -> list[int]:
    veh = ocap.vehicles[vehicle_id]
    veh_pos = veh.positions[frame]
    spread = AppState().config.OCAPS_PLY_VEHICLES_SPREAD_COORDS
    spread_list = [i - spread for i in range(spread * 2 + 1)]

    crew = []
    for i in spread_list:
        for j in spread_list:
            if (i, j) == (0, 0):
                crew.extend(ocap.positions[EntityType.UNIT][frame][(veh_pos.coordinates.x, veh_pos.coordinates.y)])
    return crew


def parse_player_vehicle_id(
        ocap: OCAP,
        player_id: int,
        frame: int,
) -> int | None:  # returns vehicle_id
    ply = ocap.players[player_id]
    spread = AppState().config.OCAPS_PLY_VEHICLES_SPREAD_COORDS
    if frame >= len(ply.positions):
        return None

    ply_pos = ply.positions[frame]
    ply_vehicles_ids = ocap.positions[EntityType.VEHICLE][frame][(ply_pos.coordinates.x, ply_pos.coordinates.y)]
    if ply_vehicles_ids:
        vehicle_id, *_ = ply_vehicles_ids
        return vehicle_id

    spread_list = [i - spread for i in range(spread * 2 + 1)]
    for i in spread_list:
        for j in spread_list:
            if (i, j) == (0, 0):
                continue

            ply_vehicle_ids = ocap.positions[EntityType.VEHICLE][frame][
                (ply_pos.coordinates.x + i, ply_pos.coordinates.y + j)
            ]
            if ply_vehicle_ids:
                vehicle_id, *_ = ply_vehicle_ids
                return vehicle_id or None


def get_game_type_from_file(path: Path) -> GameType | None:
    """
    !HARDCODE!
    Пришлось накостылять. Данных об игре нигде не написано, более чем вероятно, даже внутри файловой структуры сервера.
    Вряд ли они есть и на самом деле.
    :param path:
    :return:
    """
    if '_LTVT' in str(path).upper():
        return GameType.LTVT
    
    ocap_filename = path.name.rsplit("/")[-1]
    ocap_date = ocap_filename[:17]
    created_at = datetime.strptime(ocap_date, "%Y_%m_%d__%H_%M")

    return get_game_type(created_at)


def get_game_type(dt: datetime) -> GameType:
    """
    !HARDCODE!
    Пришлось накостылять. Данных об игре нигде не написано, более чем вероятно, даже внутри файловой структуры сервера.
    Вряд ли они есть и на самом деле.
    :param dt:
    :return:
    """

    weekday = dt.weekday()
    match weekday:
        case 1 | 2:  # Вт | Ср
            return GameType.IF
        case 3:  # Чт
            return GameType.TVT1
        case 4:  # Пт
            if dt.time() < time(20):
                return GameType.TVT1
            return GameType.TVT2
        case 5:  # Сб
            if dt.time() > time(20):
                return GameType.TVT2
            if dt.time() > time(16):
                return GameType.TVT1
            return GameType.TVT2  # Если игры ТВТ2 кончились после полуночи в сб. И не позже 16:00.
        case 6:  # Вс, если ТВТ2 кончилось после полуночи
            return GameType.TVT2
    return GameType.UNKNOWN
