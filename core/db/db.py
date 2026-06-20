import os, json
from typing import Any, overload, Literal

from asyncpg import UndefinedTableError, PostgresSyntaxError
from loguru import logger
from pydantic import BaseModel

from core.encoders import json_default_encoder
from core.settings import BotSettings
import asyncpg


async def init(config: BotSettings, **extra_kwargs: object) -> "asyncpg.Pool[Any]":
    if not config.PSQL_PATH:
        msg = "DB connection parameters not defined"
        raise RuntimeError(msg)
    return await asyncpg.create_pool(
        dsn=config.PSQL_PATH,
        init=init_connection,
        min_size=1,
        max_size=3,
        **extra_kwargs,
    )


async def init_connection[T: asyncpg.Connection[Any]](conn: T) -> T:
    await conn.set_type_codec(
        "jsonb",
        encoder=encode_json,
        decoder=json.loads,
        schema="pg_catalog",
    )

    return conn


async def migrate_up(config: BotSettings, **extra_kwargs: object):
    conn: asyncpg.Connection = await asyncpg.connect(dsn=config.PSQL_PATH, **extra_kwargs)
    try:
        migrations_in_db = await get_list(conn, "migrations")
    except UndefinedTableError:
        migrations_in_db = []
    nums_in_db = [i[0] for i in migrations_in_db]

    migrations = os.listdir(config.MIGRATIONS_PATH)
    for migration_filename in migrations:
        num, *_ = migration_filename.split("_")
        if num not in nums_in_db:
            with open(f"{config.MIGRATIONS_PATH}/{migration_filename}", "r") as fd:
                try:
                    await conn.execute(fd.read())
                    await create(conn, "migrations", data={"id": num})
                except Exception as e:
                    logger.error(f"Failed to apply migration #{num}: {repr(e)}")
    await conn.close()


def record_to_model_list[T: BaseModel](
    model_cls: type[T],
    records: list[asyncpg.Record | dict] | None,
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


# TODO Интегрирование пагинации
# def record_to_model_pagination[T: BaseModel](
#     model_cls: type[T],
#     records: PaginatedRecords,
# ) -> PaginationSchema[T]:
#     items = [record_to_model(model_cls, i) for i in records.items]
#     return PaginationSchema[T].model_validate(
#         records.model_dump(exclude={"items"}) | {"items": items},
#     )


@overload
def record_to_model[T: BaseModel](model_cls: type[T], record: asyncpg.Record | dict) -> T: ...


@overload
def record_to_model[T: BaseModel](model_cls: type[BaseModel], record: None) -> None: ...


def record_to_model[T: BaseModel](model_cls: type[T], record: asyncpg.Record | dict | None) -> T | None:
    if record:
        return model_cls.model_validate(dict(record))

    return None


async def get(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int,
    fields: list[str] | None = None,
    additional_where: list[str] | None = None,
    additional_values: list[Any] | None = None,
    for_update: bool = False,
    left_outer_join: list[str] | None = None,
) -> asyncpg.Record | None:
    additional_values = additional_values or []
    additional_where = additional_where or []

    values = [pk]
    select_fields = ", ".join(fields) if fields else "*"
    where = "id"

    values = values + additional_values
    _where = " AND ".join([f"{k} = ${i + 1}" for i, k in enumerate([where, *additional_where])])

    left_join_query = ""
    if left_outer_join is not None:
        left_join_query = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])

    query = f"SELECT {select_fields} FROM {table} {left_join_query} WHERE {_where} {'FOR UPDATE' if for_update else ''}"
    try:
        return await conn.fetchrow(query, *values)
    except Exception as e:
        logger.exception(f"Query failed (({repr(e)})):\n{query}")
        raise


@overload
async def get_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    return_rows: Literal[False] = False,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
    for_update: bool = False,
) -> asyncpg.Record | None: ...


@overload
async def get_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    return_rows: Literal[True] = True,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
    for_update: bool = False,
) -> list[asyncpg.Record] | None: ...


async def get_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str,
    values: list[Any] | None = None,
    fields: list[str] | None = None,
    order_by: list[str] | None = None,
    return_rows: bool = False,
    left_outer_join: list[str] | None = None,
    group_by: list[str] | None = None,
    for_update: bool = False,
) -> asyncpg.Record | list[asyncpg.Record] | None:
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

    query = f"""
            SELECT {select_fields} 
            FROM {table} 
            {left_join_query} 
            WHERE {where} 
            {group_by_query} 
            {order_by_query}              
            {"FOR UPDATE" if for_update else ""}
        """

    execute = conn.fetch if return_rows else conn.fetchrow
    try:
        return await execute(query, *values)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def get_list(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str | list[str] | None = None,
    values: list[Any] | None = None,
    order: list[str] | None = None,
    group: list[str] | None = None,
    fields: list[str] | None = None,
    left_outer_join: list[str] | None = None,
) -> list[asyncpg.Record]:
    values = values or []
    select_fields = ", ".join(fields) if fields else "*"
    where_query, limit_query, offset_query, order_query, group_query, left_join_query = "", "", "", "", "", ""

    if left_outer_join is not None:
        left_join_query = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])
    if where:
        where_ = " AND ".join(where) if isinstance(where, list) else where
        where_query = f"WHERE {where_}"
    if order:
        order_query = "ORDER BY " + ", ".join([f"{i[1:]} DESC" if i.startswith("-") else i for i in order])
    if group:
        group_query = f"GROUP BY {','.join(group)}"
    query = (
        f"SELECT {select_fields} "
        f"FROM {table} {left_join_query} {where_query} {group_query} {order_query} {limit_query} {offset_query}"
    )
    try:
        return await conn.fetch(query, *values)
    except:
        logger.exception(f"Query {query} failed")
        raise


# async def get_paginated(
#     conn: "asyncpg.Connection[Any]",
#     table: str,
#     where: str | list[str] | None = None,
#     limit: int | None = None,  # None по умолчанию, 0 без ограничения
#     offset: int | None = None,
#     values: list[Any] | None = None,
#     order: list[str] | None = None,
#     group: list[str] | None = None,
#     fields: list[str] | None = None,
#     left_outer_join: list[str] | None = None,
# ) -> PaginatedRecords:
#     values = values or []
#     limit = settings.MAX_RECORDS_PER_PAGE if limit is None else limit
#     select_fields = ", ".join(fields) if fields else "*"
#     where_query, limit_query, offset_query, order_query, group_query, left_join = (
#         "",
#         f"LIMIT {limit}" if limit else "",
#         "",
#         "",
#         "",
#         "",
#     )
#     if left_outer_join:
#         left_join = " ".join([f"LEFT JOIN {i}" for i in left_outer_join])
#     if where:
#         where_ = " AND ".join(where) if isinstance(where, list) else where
#         where_query = f"WHERE {where_}"
#     if offset:
#         offset_query = f"OFFSET {(offset - 1) * limit}"
#     if order:
#         order_query = "ORDER BY " + ", ".join([f"{i[1:]} DESC" if i.startswith("-") else i for i in order])
#     if group:
#         group_query = f"GROUP BY {','.join(group)}"
#     query = (
#         f"SELECT {select_fields} "
#         f"FROM {table} {left_join} {where_query} {group_query} {order_query} {limit_query} {offset_query}"
#     )
#     query_total_items = f"SELECT COUNT(*) AS total_items FROM {table} {left_join} {where_query} {group_query}"
#     try:
#         total_items_result = await conn.fetchrow(query_total_items, *values)
#         total_items = total_items_result["total_items"] if total_items_result else 0
#         result = await conn.fetch(query, *values)
#         _per_page = limit or total_items or 1
#         paginated_records = {
#             "items": result,
#             "total_pages": ceil(total_items / _per_page),
#             "current_page": offset,
#             "page_items": len(result),
#             "total_items": total_items,
#         }
#         return PaginatedRecords(**paginated_records)
#     except:
#         logger.exception(f"Query {query} failed")
#         raise


# async def get_paginated_query(
#     conn: "asyncpg.Connection[Any]",
#     stmt: str,
#     values: list[Any],
#     limit: int | None = None,
#     offset: int | None = None,
#     order: list[str] | None = None,
# ) -> PaginatedRecords:
#     limit = limit or 20
#     query_total_items = f"SELECT COUNT(*) AS total_items FROM ({stmt})"
#     order_query = ""
#     pagination_query = f"LIMIT {limit}"
#
#     if offset:
#         pagination_query = f"{pagination_query} OFFSET {(offset - 1) * limit}"
#     if order:
#         order_query = "ORDER BY " + ", ".join([f"{i[1:]} DESC" if i.startswith("-") else i for i in order])
#
#     query = f"{stmt} {order_query} {pagination_query}"
#
#     try:
#         total_items_result = await conn.fetchrow(query_total_items, *values)
#         total_items = total_items_result["total_items"]
#         result = await conn.fetch(query, *values)
#         paginated_records = {
#             "items": result,
#             "total_pages": ceil(total_items / limit),
#             "current_page": offset,
#             "page_items": len(result),
#             "total_items": total_items,
#         }
#         return PaginatedRecords(**paginated_records)
#     except:
#         logger.exception(f"Query {query} failed")
#         raise


_empty: Any = object()


async def get_raw(
    conn: "asyncpg.Connection[Any]",
    stmt: str,
    values: list[Any] = _empty,
) -> list[asyncpg.Record]:
    if values is _empty:
        values = []

    try:
        return await conn.fetch(stmt, *values)
    except:
        logger.exception(f"Query {stmt} failed")
        raise

async def get_raw_one(
    conn: "asyncpg.Connection[Any]",
    stmt: str,
    values: list[Any] = _empty,
) -> asyncpg.Record:
    if values is _empty:
        values = []

    try:
        return await conn.fetchrow(stmt, *values)
    except:
        logger.exception(f"Query {stmt} failed")
        raise


async def get_total(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str | None = None,
    values: list[Any] | None = None,
    group_by: list[str] | None = None,
) -> int:
    values = values if values else []
    where_query = ""
    if where:
        where_query = f"WHERE {where}"
    group_query = ""
    if group_by:
        group_query = f"GROUP BY {','.join(group_by)}"
    query = f"SELECT count(*) as count FROM {table} {where_query} {group_query}"
    try:
        result = await conn.fetchrow(query, *values)
        return result["count"]
    except:
        logger.exception(f"Query {query} failed")
        raise


async def exists(
    conn: "asyncpg.Connection[Any]",
    table: str,
    where: str | None = None,
    values: list[Any] | None = None,
) -> bool:
    where_query = ""
    if where:
        where_query = f"WHERE {where}"
    query = f"SELECT * FROM {table} {where_query}"
    try:
        return bool(
            await conn.fetchrow(
                query,
                *values,
            ),
        )
    except:
        logger.exception(f"Query {query} failed")
        raise


async def create(
    conn: "asyncpg.Connection[Any]",
    table: str,
    data: dict[str, Any],
    insert_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
    fields: list[str] | None = None,
    on_conflict: str | None = None,
) -> asyncpg.Record | None:
    fields = fields or []
    field_names: list[str] = []
    placeholders: list[str] = []
    values: list[str] = []
    idx = 1
    return_fields = ", ".join(fields) if fields else "*"
    on_conflict = f"ON CONFLICT {on_conflict}" if on_conflict else ""
    for key in data:
        if insert_fields and key not in insert_fields:
            continue

        if ignore_fields and key in ignore_fields:
            continue

        field_names.append(key)
        placeholders.append(f"${idx}")
        values.append(data[key])
        idx += 1
    query = f"""
            INSERT INTO {table} 
                ({", ".join(field_names)}) 
            VALUES 
                ({", ".join(placeholders)}) 
            {on_conflict} RETURNING {return_fields}
        """
    try:
        return await conn.fetchrow(query, *values)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def create_list(
    conn: "asyncpg.Connection[Any]",
    table: str,
    data: list[dict[str, Any]],
    return_fields: list[str] | None = None,
    on_conflict: str | None = None,
) -> list[asyncpg.Record] | None:
    # Добавляет несколько значений в БД за раз
    # Значения передаются в словаре, ключ - список (длины списков должны совпадать)
    # Словари в data должны обладать идентичными ключами.
    # Не поддерживает тип `None` почему-то, asyncpg ругается.

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
                unnest($1::{table}[]) as d
        )
        {on_conflict_str}
        RETURNING {", ".join(return_fields) if return_fields else "*"}
    """
    try:
        return await conn.fetch(query, data)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def update(
    conn: "asyncpg.Connection[Any]",
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
    updated_by: int | None = None,
) -> asyncpg.Record | None:
    if pk is None:
        msg = "pk or uuid required"
        raise RuntimeError(msg)

    fields = fields or []
    placeholders: list[str] = []
    idx = len(additional_values) + 1 if additional_values else 1

    values = additional_values or []
    values.append(pk)
    where = f"id = ${idx}"
    idx += 1
    return_fields = ", ".join(fields) if fields else "*"

    for key in data:
        if with_updated_at and key == "updated_at":
            continue

        if updated_by and key == "updated_by":
            continue

        if update_fields and key not in update_fields:
            continue

        if ignore_fields and key in ignore_fields:
            continue

        placeholders.append(f"{key} = ${idx}")
        values.append(data[key])
        idx += 1

    if with_updated_at:
        placeholders.append("updated_at = (now() at time zone 'utc')")
    if with_deleted_at:
        placeholders.append("deleted_at = (now() at time zone 'utc')")
    if updated_by:
        placeholders.append(f"updated_by = ${idx}")
        values.append(updated_by)
        idx += 1

    update_set = ", ".join(placeholders)
    if additional_where:
        where = f"{where} AND {' AND '.join(additional_where)}"
    query = f"UPDATE {table} SET {update_set} WHERE {where} RETURNING {return_fields}"

    try:
        return await conn.fetchrow(query, *values)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def update_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    data: dict[str, Any],
    where: str,
    values: list[Any] | None = None,
    update_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
    fields: list[str] | None = None,
    with_updated_at: bool = True,
    with_deleted_at: bool = False,
    return_rows: bool = False,
) -> asyncpg.Record | None:
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

        placeholders.append(f"{key} = ${idx}")
        update_values.append(data[key])
        idx += 1

    if with_updated_at:
        placeholders.append("updated_at = (now() at time zone 'utc')")

    if with_deleted_at:
        placeholders.append("deleted_at = (now() at time zone 'utc')")

    update = ", ".join(placeholders)
    values.extend(update_values)
    query = f"UPDATE {table} SET {update} WHERE {where} RETURNING {return_fields}"

    execute = conn.fetchrow

    if return_rows:
        execute = conn.fetch

    try:
        return await execute(query, *values)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def disable_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int | None = None,
    updated_by: int | None = None,
    where: list[str] | None = None,
    values: list[Any] | None = None,
) -> asyncpg.Record | None:
    idx = len(values) + 1 if values else 1
    values_ = values or []
    where_ = where or []

    if pk:
        values_.append(pk)
        where_.append(f"id = ${idx}")
        idx += 1
    if updated_by:
        values_.append(updated_by)

    query = f"""
        UPDATE {table} 
        SET 
            deleted_at = (NOW() at time zone 'utc')
            {f", updated_by = ${idx}" if updated_by else ""}
        WHERE {" AND ".join(where_)}
        RETURNING *
    """
    try:
        return await conn.fetchrow(
            query,
            *values_,
        )
    except:
        logger.exception(f"Query {query} failed")
        raise


async def delete_by_where(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int | None = None,
    where: list[str] | None = None,
    values: list[Any] | None = None,
) -> asyncpg.Record | None:
    idx = len(values) + 1 if values else 1
    values_ = values or []
    where_ = where or []

    if pk:
        values_.append(pk)
        where_.append(f"id = ${idx}")

    query = f"""
        DELETE FROM {table} 
        WHERE {" AND ".join(where_)}
        RETURNING *
    """
    try:
        return await conn.fetchrow(
            query,
            *values_,
        )
    except:
        logger.exception(f"Query {query} failed")
        raise


async def delete(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int,
    fields: list[str] | None = None,
) -> asyncpg.Record | None:
    fields = fields or []
    return_fields = ", ".join(fields) if fields else "*"
    where = "id = $1"
    query = f"DELETE FROM {table} WHERE {where} RETURNING {return_fields}"
    try:
        return await conn.fetchrow(query, pk)
    except:
        logger.exception(f"Query {query} failed")
        raise


async def disable(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int,
    data: dict[str, Any] | None = None,
    fields: list[str] | None = None,
) -> asyncpg.Record | None:
    return await update(
        conn,
        table=table,
        pk=pk,
        data=data or {},
        fields=fields,
        with_updated_at=False,
        with_deleted_at=True,
    )


async def enable(
    conn: "asyncpg.Connection[Any]",
    table: str,
    pk: int,
    fields: list[str] | None = None,
) -> asyncpg.Record | None:
    fields = fields or []
    return_fields = ", ".join(fields) if fields else "*"
    where = "id = $1"
    query = f"UPDATE {table} SET deleted_at = null WHERE {where} RETURNING {return_fields}"
    try:
        return await conn.fetchrow(query, pk)
    except:
        logger.exception(f"Query {query} failed")
        raise


def encode_json(value: object) -> str:
    return json.dumps(value, default=json_default_encoder)
