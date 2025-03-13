from datetime import datetime

from pydantic import BaseModel

from logic.kill_log.misc import GameType


class OcapDBForm(BaseModel):
    filename: str
    length_seconds: int
    game_type: str


class OcapDB(BaseModel):
    id: int
    filename: str
    length_seconds: int
    created_at: datetime


class OcapPlayerForm(BaseModel):
    game_id: int
    name: str
    group_name: str
    side: str
    dead_at_frame: int | None = None


class OcapKillForm(BaseModel):
    killer_id: int
    killed_id: int | None = None
    killer_vehicle: str | None = None
    killed_vehicle: str | None = None
    team_kill: bool
    frame: int
    weapon: str
    weapon_is_vehicle: bool
    distance: int


class OcapForm(BaseModel):
    ocap: OcapDBForm
    players: list[OcapPlayerForm]
    kills: list[OcapKillForm]


class OcapKill(BaseModel):
    weapon: str
    weapon_is_vehicle: bool
    victim_name: str
    victim_is_vehicle: bool
    team_kill: bool
    distance: int


class OcapPlayer(BaseModel):
    name: str
    group_name: str
    killed_by: str | None = None
    kills: list[OcapKill] = []


class OcapDetail(BaseModel):
    id: int
    filename: str
    game_type: GameType
    length_seconds: int
    players: list[OcapPlayer]
    created_at: datetime
