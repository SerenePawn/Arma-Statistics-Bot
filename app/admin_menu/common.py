from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from app.admin_menu.misc import admin_menu_edit

router = Router()


@router.callback_query(F.data == 'admin_common_cancel')
async def admin_common_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await state.clear()

    await admin_menu_edit(callback.message)
