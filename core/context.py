import uuid
from contextvars import ContextVar


class AppRequest:
    _id: ContextVar[str] = ContextVar("request_id", default="--INTERNAL--")

    @classmethod
    def gen_id(cls) -> None:
        cls._id.set(str(uuid.uuid4()))

    @classmethod
    def id(cls) -> str:
        return cls._id.get()
