from enum import StrEnum

from pydantic import BaseModel


class RequestType(StrEnum):
    JOIN = "join"
    FRIEND = "friend"


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"


class SquadRequest(BaseModel):
    id: int
    squad_id: int
    telegram_id: int
    player_id: int
    request_type: RequestType
    status: RequestStatus
    created_at: object
    resolved_at: object | None = None
