import os
from sqlite3 import OperationalError
from typing import Any, overload

import aiosqlite as sqlite
from aiosqlite import Cursor, Row
from loguru import logger
from pydantic import BaseModel

from core.settings import BotSettings

"""
Тому, кто решил спиздить код: функции прикручены от другой БД при помощи некоторого шаманства. 
Не удивляйся, если нихуя из фич не работает и половину кода нужно будет переписывать))
Хотя я тут и так дохера сделал, мб только небольшую часть нужно переписать.
"""


async def init(config: BotSettings, **extra_kwargs: object) -> "sqlite.Connection":
    logger.info(f"Init db conn")
    if not config.SQLITE_PATH:
        msg = "DB connection parameters not defined"
        raise RuntimeError(msg)
    conn = await sqlite.connect(
        config.SQLITE_PATH,
        **extra_kwargs,
    )
    conn.row_factory = __row_factory_dict
    return conn


def __row_factory_dict(cursor: Cursor, row: Row) -> dict:
    data = {}
    for idx, col in enumerate(cursor.description):
        data[col[0].replace("()", "")] = row[idx]
    return data


async def migrate_up(config: BotSettings, **extra_kwargs: object):
    async with sqlite.connect(config.SQLITE_PATH, **extra_kwargs) as conn:
        try:
            migrations_in_db = await get_list(conn, "migrations")
        except OperationalError:
            migrations_in_db = []
        nums_in_db = [i[0] for i in migrations_in_db]

        migrations = os.listdir(config.MIGRATIONS_PATH)
        for migration_filename in migrations:
            num, *_ = migration_filename.split("_")
            if num not in nums_in_db:
                with open(f"{config.MIGRATIONS_PATH}/{migration_filename}", "r") as fd:
                    try:
                        await conn.executescript(fd.read())
                        await create(conn, "migrations", data={"id": num})
                    except:
                        raise


def record_to_model_list[T: BaseModel](
    model_cls: type[T],
    records: list[sqlite.Row] | None,
) -> list[T]:
    if records:
        return [
            record_to_model(
                model_cls,
                x,
            )
            for x in records
        ]
    return []


@overload
def record_to_model[T: BaseModel](model_cls: type[T], record: sqlite.Row) -> T: ...


@overload
def record_to_model[T: BaseModel](model_cls: type[BaseModel], record: None) -> None: ...


def record_to_model[T: BaseModel](model_cls: type[T], record: sqlite.Row | None) -> T | None:
    if record:
        return model_cls.model_validate(dict(record))

    return None


async def get(
    conn: "sqlite.Connection",
    table: str,
    pk: int,
    fields: list[str] | None = None,
    additional_where: list[str] | None = None,
    additional_values: list[Any] | None = None,
    for_update: bool = False,
    left_outer_join: list[str] | None = None,
) -> sqlite.Row | None:
    if pk is None:
        msg = "pk or uuid required"
        raise RuntimeError(msg)

    additional_values = additional_values or []
    additional_where = additional_where or []

    values = [pk]
    select_fields = ", ".join(fields) if fields else "*"
    where = "id" if pk is not None else "uuid"

    values = values + additional_values
    _where = " AND ".join([f"{i} = ?" for i in [where, *additional_where]])

    left_join_query = ""
    if left_outer_join is not None:
        left_join_query = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])

    query = f"SELECT {select_fields} FROM {table} {left_join_query} WHERE {_where} {'for_update' if for_update else ''}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result_query = await conn.execute_fetchall(query, values)
    if not result_query:
        return None

    result, *_ = result_query
    return result


@overload
async def get_by_where(
    conn: "sqlite.Connection",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
) -> list[sqlite.Row] | None: ...


@overload
async def get_by_where(
    conn: "sqlite.Connection",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
) -> list[sqlite.Row] | None: ...


async def get_by_where(
    conn: "sqlite.Connection",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
) -> list[sqlite.Row] | None:
    values = values or []
    select_fields = ", ".join(fields) if fields else "*"
    order_by_query = ""
    if order_by:
        order_by_query = "ORDER BY " + ", ".join([f"{i[1:]} DESC" if i.startswith("-") else i for i in order_by])

    left_join_query = ""
    if left_outer_join is not None:
        left_join_query = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])

    group_by_query = ""
    if group_by:
        group_by_query = f"GROUP BY {','.join(group_by)}"

    query = f"SELECT {select_fields} FROM {table} {left_join_query} WHERE {where} {order_by_query} {group_by_query}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result = await conn.execute_fetchall(query, values)
    if not result:
        return None

    return list(result)


async def get_list(
    conn: "sqlite.Connection",
    table: str,
    where: str | None = None,
    values: list[Any] | None = None,
    order: list[str] | None = None,
    group: list[str] | None = None,
    fields: list[str] | None = None,
    left_outer_join: list[str] | None = None,
    limit: int | None = None,
    page: int | None = None
) -> list[sqlite.Row]:
    values = values or []
    select_fields = ", ".join(fields) if fields else "*"
    where_query, limit_query, offset_query, order_query, group_query, left_join_query = "", "", "", "", "", ""

    if left_outer_join is not None:
        left_join_query = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])
    if where:
        where_query = f"WHERE {where}"
    if order:
        order_query = "ORDER BY " + ", ".join([f"{i[1:]} DESC" if i.startswith("-") else i for i in order])
    if group:
        group_query = f"GROUP BY {','.join(group)}"
    if limit:
        limit_query = f"LIMIT {limit}"
    if limit and page:
        offset_query = f"OFFSET {limit * (page - 1)}"
    query = (
        f"SELECT {select_fields} "
        f"FROM {table} {left_join_query} {where_query} {order_query} {group_query} {limit_query} {offset_query}"
    )
    logger.debug(f"DB q='{query.strip()}' | {values=}")
    try:
        result = await conn.execute_fetchall(query, *values)
        return list(result)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def get_total(
    conn: "sqlite.Connection",
    table: str,
    where: str | None = None,
    values: list[Any] | None = None,
    group_by: list[str] | None = None,
) -> int:
    values = values if values else []
    where_query = ""
    if where:
        where_query = f"WHERE {where}"
    if group_by:
        group_query = f"GROUP BY {','.join(group_by)}"
    query = f"SELECT count(*) as count FROM {table} {where_query}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result, *_ = await conn.execute_fetchall(query, *values)
    return result["count"]


async def exists(
    conn: "sqlite.Connection",
    table: str,
    where: str | None = None,
    values: list[Any] | None = None,
) -> bool:
    where_query = ""
    if where:
        where_query = f"WHERE {where}"
    query = f"SELECT * FROM {table} {where_query}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")
    try:
        return bool(
            await conn.execute_fetchall(
                query,
                *values,
            ),
        )
    except:
        logger.exception(f"Query {query} failed")
        raise


async def create(
    conn: "sqlite.Connection",
    table: str,
    data: dict[str, Any],
    insert_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
    fields: list[str] | None = None,
    on_conflict: str | None = None,
    commit: bool = True
) -> sqlite.Row | None:
    fields = fields or []
    field_names: list[str] = []
    placeholders: list[str] = []
    values: list[str] = []
    return_fields = ", ".join(fields) if fields else "*"
    on_conflict = f"ON CONFLICT {on_conflict}" if on_conflict else ""
    for key in data:
        if insert_fields and key not in insert_fields:
            continue

        if ignore_fields and key in ignore_fields:
            continue

        field_names.append(key)
        placeholders.append(f"?")
        values.append(data[key])
    query = f"""
        INSERT INTO {table} 
            ({", ".join(field_names)}) 
        VALUES 
            ({", ".join(placeholders)}) 
        {on_conflict} RETURNING {return_fields}
    """
    logger.debug(f"DB q='{query.strip()}' | {values=}")
    try:
        result = await conn.execute_insert(query, values)
        if commit:
            await conn.commit()
        return result
    except:
        logger.exception(f"Query {query} failed")
        raise


async def create_list(
    conn: "sqlite.Connection",
    table: str,
    data: list[dict[str, Any]],
    return_fields: list[str] | None = None,
    on_conflict: str | None = None,
) -> list[int] | None:
    # Добавляет несколько значений в БД за раз
    # Значения передаются в словаре, ключ - список (длины списков должны совпадать)
    # Словари в data должны обладать идентичными ключами.
    # Не поддерживает тип `None` почему-то, sqlite ругается.

    if not data:
        return []

    on_conflict_str = ""
    if on_conflict:
        on_conflict_str = f"""
            ON CONFLICT {on_conflict}
        """

    first_data = data[0]
    query = f"""
        INSERT INTO {table}
            ({", ".join(first_data.keys())})
        (
            SELECT {", ".join(first_data.keys())}
            FROM
                unnest(?::{table}[]) as d
        )
        {on_conflict_str}
        RETURNING {", ".join(return_fields) if return_fields else "*"}
    """
    logger.debug(f"DB q='{query.strip()}'")

    result = await conn.execute_fetchall(query, data)
    await conn.commit()
    return [i["last_insert_rowid"] for i in result]


async def update(
    conn: "sqlite.Connection",
    table: str,
    data: dict[str, Any],
    pk: int,
    update_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
    additional_where: list[str] | None = None,
    additional_values: list[Any] | None = None,
    fields: list[str] | None = None,
    with_updated_at: bool = True,
    with_deleted_at: bool = False,
) -> sqlite.Row | None:
    if pk is None:
        msg = "pk or uuid required"
        raise RuntimeError(msg)

    fields = fields or []
    placeholders: list[str] = []
    idx = len(additional_values) + 1 if additional_values else 1

    values = additional_values or []
    where = f"id = ?"
    idx += 1
    return_fields = ", ".join(fields) if fields else "*"

    for key in data:
        if with_updated_at and key == "updated_at":
            continue

        if update_fields and key not in update_fields:
            continue

        if ignore_fields and key in ignore_fields:
            continue

        placeholders.append(f"{key} = ?")
        values.append(data[key])
        idx += 1

    values.append(pk)  # Тут прибавляем значение id. Ебучий сикулайт...
    if with_updated_at:
        placeholders.append("updated_at = CURRENT_TIMESTAMP")
    if with_deleted_at:
        placeholders.append("deleted_at = CURRENT_TIMESTAMP")

    update_set = ", ".join(placeholders)
    if additional_where:
        where = f"{where} AND {' AND '.join(additional_where)}"
    query = f"UPDATE {table} SET {update_set} WHERE {where} RETURNING {return_fields}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result_query = await conn.execute_fetchall(query, values)
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result


async def update_by_where(
    conn: "sqlite.Connection",
    table: str,
    data: dict[str, Any],
    where: str,
    values: list[Any] | None = None,
    update_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
    fields: list[str] | None = None,
    with_updated_at: bool = True,
    with_deleted_at: bool = False,
) -> sqlite.Row | None:
    return_fields = ", ".join(fields) if fields else "*"
    placeholders: list[str] = []
    update_values: list[str] = []
    values = values or []
    idx = len(values) + 1
    for key in data:
        if with_updated_at and key == "updated_at":
            continue

        if with_deleted_at and key == "deleted_at":
            continue

        if update_fields and key not in update_fields:
            continue

        if ignore_fields and key in ignore_fields:
            continue

        placeholders.append(f"{key} = ?")
        update_values.append(data[key])
        idx += 1

    if with_updated_at:
        placeholders.append("updated_at = CURRENT_TIMESTAMP")

    if with_deleted_at:
        placeholders.append("deleted_at = CURRENT_TIMESTAMP")

    update = ", ".join(placeholders)
    values.extend(update_values)
    query = f"UPDATE {table} SET {update} WHERE {where} RETURNING {return_fields}"
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result_query = await conn.execute_fetchall(query, values)
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result


async def disable_by_where(
    conn: "sqlite.Connection",
    table: str,
    pk: int | None = None,
    updated_by: int | None = None,
    where: list[str] | None = None,
    values: list[Any] | None = None,
) -> sqlite.Row | None:
    idx = len(values) + 1 if values else 1
    values_ = values or []
    where_ = where or []

    if pk:
        values_.append(pk)
        where_.append(f"id = ?")
        idx += 1
    if updated_by:
        values_.append(updated_by)

    query = f"""
        UPDATE {table} 
        SET 
            deleted_at = CURRENT_TIMESTAMP
            {f", updated_by = ?" if updated_by else ""}
        WHERE {" AND ".join(where_)}
        RETURNING *
    """
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result_query = await conn.execute_fetchall(query, values)
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result


async def delete_by_where(
    conn: "sqlite.Connection",
    table: str,
    pk: int | None = None,
    where: list[str] | None = None,
    values: list[Any] | None = None,
) -> sqlite.Row | None:
    values_ = values or []
    where_ = where or []

    if pk:
        where_.append("id = ?")
        values_.append(pk)

    query = f"""
        DELETE FROM {table} 
        WHERE {" AND ".join(where_)}
        RETURNING *
    """
    logger.debug(f"DB q='{query.strip()}' | {values=}")

    result_query = await conn.execute_fetchall(query, values)
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result


async def delete(
    conn: "sqlite.Connection",
    table: str,
    pk: int,
    fields: list[str] | None = None,
) -> sqlite.Row | None:
    if pk is None:
        raise RuntimeError("pk or uuid required")

    fields = fields or []
    return_fields = ", ".join(fields) if fields else "*"
    where = "id = ?"
    query = f"DELETE FROM {table} WHERE {where} RETURNING {return_fields}"
    logger.debug(f"DB q='{query.strip()}'")

    result_query = await conn.execute_fetchall(query, [pk])
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result


async def disable(
    conn: "sqlite.Connection",
    table: str,
    pk: int,
    data: dict[str, Any] | None = None,
    fields: list[str] | None = None,
) -> sqlite.Row | None:
    result = await update(
        conn,
        table=table,
        pk=pk,
        data=data or {},
        fields=fields,
        with_updated_at=False,
        with_deleted_at=True,
    )
    await conn.commit()
    return result


async def enable(
    conn: "sqlite.Connection",
    table: str,
    pk: int,
    fields: list[str] | None = None,
) -> sqlite.Row | None:
    if pk is None:
        msg = "pk or uuid required"
        raise RuntimeError(msg)

    fields = fields or []
    return_fields = ", ".join(fields) if fields else "*"
    where = "id = ?"
    query = f"UPDATE {table} SET deleted_at = null WHERE {where} RETURNING {return_fields}"
    logger.debug(f"DB q='{query.strip()}'")

    result_query = await conn.execute_fetchall(query, [pk])
    if not result_query:
        return None

    result, *_ = result_query
    await conn.commit()
    return result
