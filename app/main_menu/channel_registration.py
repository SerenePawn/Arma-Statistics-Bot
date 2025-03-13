from contextlib import suppress

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from core.app_state import AppState
from logic.squads import db as squads_db

from app.main_menu.fsm import SquadFSM
from app.main_menu.misc import main_menu_open
from logic.squads.models import SquadForm

router = Router()


@router.message(SquadFSM.name)
async def fsm_register_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(SquadFSM.tags)
    # Чистки последних сбщ
    with suppress(TelegramBadRequest):
        await message.delete()
    registration_message = (await state.get_data())["registration_message"]

    await registration_message.edit_text(
        "(2/2) Регистрация канала в боте.\n"
        "Введите тэги вашего отряда через запятую. Оставьте без запятых, если тэг один.\n"
        "(Например, для игрока `[TAG]Player` это `[TAG]`. "
        "Для игроков (кадетов) `[=TAG=]` - нужно ввести `[TAG], [=TAG=]`. Регистр не важен.)",
    )


@router.message(SquadFSM.tags)
async def fsm_register_tag(message: types.Message, state: FSMContext):
    await state.update_data(tags=message.text)
    # Чистки последних сбщ
    with suppress(TelegramBadRequest):
        await message.delete()
    await (await state.get_data())["registration_message"].delete()
    await state.update_data(registration_message=None)

    data = await state.get_data()
    await squads_db.create(
        AppState().conn,
        SquadForm(
            telegram_chat_id=message.chat.id,
            telegram_chat_thread_id=message.message_thread_id,
            **data
        )
    )

    await state.clear()
    await main_menu_open(message)
