from datetime import datetime, time
from typing import (
    Optional,
    List,
    TypeVar
)


# import core.db.models_db as db
from core.models.common import (
    CommonSearchUpdateModel,
    CommonModel
)

T = TypeVar('T')


class UserModel(CommonModel):
    words_to_remind: list[int]
    words_to_remind_count: int
    words_to_remind_time: time
    to_send_words_time: time
    status: str
    lang_code: str
    ctime: Optional[datetime]

    class Meta:
        table: str = 'users'


class UserSearchUpdateModel(CommonSearchUpdateModel):
    words_to_remind: Optional[list[int]]
    words_to_remind_count: Optional[int]
    words_to_remind_time: Optional[time]
    to_send_words_time: Optional[time]
    status: Optional[str]
    lang_code: Optional[str]
    ctime: Optional[datetime]

    class Meta:
        table: str = 'users'
        main_model: UserModel = UserModel


class WordsModel(CommonModel):
    id: Optional[int]
    val: str
    ctime: datetime

    class Meta:
        table: str = 'words'


class WordsSearchUpdateModel(CommonSearchUpdateModel):
    id: Optional[int]
    val: Optional[str]
    ctime: Optional[datetime]

    class Meta:
        table: str = 'words'
        main_model: WordsModel = WordsModel

    async def select_reminded(self, where: list[str]) -> List[T]:
        vals = [f"'{i}'" for i in where]
        res = await db.mgr.get_data_all(self.Meta.table, where=f"val in ({', '.join(vals)})")
        return [self.Meta.main_model(**i) for i in res]
