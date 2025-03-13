from contextlib import suppress

from aiogram import types, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.admin_menu.fsm import AdminFSM
from app.admin_menu.misc import admin_menu_edit
from core.app_state import AppState
from logic.squads import db as squads_db

router = Router()


@router.callback_query(F.data == 'admin_menu_settings_name_tag')
async def admin_menu_settings_name_tag(callback: CallbackQuery, state: FSMContext):
    app_state = AppState()
    operational_markup = [
        InlineKeyboardButton(text="Отмена", callback_data="admin_common_cancel"),
        InlineKeyboardButton(text="Подтвердить", callback_data="admin_menu_settings_name_tag_confirm")
    ]

    squad = await squads_db.get_by_chat(app_state.conn, callback.message.chat.id, callback.message.message_thread_id)
    tags_markup = {
        i: [InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"admin_menu_settings_delete_{i}")]
        for i in squad.tags
    }

    name_tag_msg = await callback.message.edit_text(
        text="Введите тэг отряда в чат\nЧтобы убрать отряд, нажмите кнопку с тэгом",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            *tags_markup.values(),
            operational_markup,
        ])
    )

    await state.set_state(AdminFSM.name_tag)
    await state.update_data(
        squad=squad,
        name_tag_msg=name_tag_msg,
        del_tags=[],
        new_tags=[],
        tags_markup=tags_markup,
        operational_markup=operational_markup,
    )


@router.message(AdminFSM.name_tag)
async def fsm_register_tag_name_tag(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Чистки последних сбщ
    with suppress(TelegramBadRequest):
        await message.delete()

    new_tags = data.get("new_tags")
    new_tags.append(message.text)
    await state.update_data(new_tags=new_tags)

    name_tag_msg = data["name_tag_msg"]
    await name_tag_msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        *[v for k, v in data["tags_markup"].items() if k not in data["del_tags"]],
        *[
            [InlineKeyboardButton(text=f"Удалить *{i}", callback_data=f"admin_menu_settings_delete_tmp_{i}")]
            for i in new_tags
        ],
        data["operational_markup"],
    ]))


@router.callback_query(F.data.startswith("admin_menu_settings_delete_"))
async def admin_menu_settings_name_tag_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    del_data = callback.data.replace("admin_menu_settings_delete_", "")
    new_tags = data["new_tags"]
    total_del_tags = data["del_tags"] + [del_data]
    old_markup = [k for k in data["tags_markup"] if k not in total_del_tags]

    name_tag_msg = data["name_tag_msg"]
    if len(new_tags + old_markup) < 1:
        await name_tag_msg.edit_text(
            "Введите тэг отряда в чат\nЧтобы убрать отряд, нажмите кнопку с тэгом"
            "\n\nВы не можете оставить менее 1-го тэга",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [data["operational_markup"][0]]
            ])
        )
        return

    if "tmp_" in del_data:
        del_data = del_data.replace("tmp_", "")
        new_tags = [i for i in data["new_tags"] if i != del_data]
        await state.update_data(new_tags=new_tags)
    else:
        await state.update_data(tags_markup={k: v for k, v in data["tags_markup"].items() if k != del_data})
        await state.update_data(del_tags=total_del_tags)

    await name_tag_msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        *[v for k, v in data["tags_markup"].items() if k not in total_del_tags],
        *[
            [InlineKeyboardButton(text=f"Удалить *{i}", callback_data=f"admin_menu_settings_delete_tmp_{i}")]
            for i in new_tags
        ],
        data["operational_markup"],
    ]))


@router.callback_query(F.data == 'admin_menu_settings_name_tag_confirm')
async def admin_menu_settings_name_tag_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        tags_to_del = data["del_tags"]
        tags_to_save = [i for i in data["tags_markup"] if i not in tags_to_del]
        tags_to_save.extend([i for i in data["new_tags"]])

        await squads_db.update(AppState().conn, data["squad"].id, tags=",".join(tags_to_save))

        await state.set_state(None)
        await state.clear()
    except KeyError:
        raise

    await admin_menu_edit(callback.message)
