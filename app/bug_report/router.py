from math import ceil

from aiogram import types, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.utils.formatting import Text, Bold, as_list

from app.bug_report.fsm import BugFSM
from core.app_state import AppState
from logic.bug_reports import db as bugs_db
from logic.bug_reports.models import BugReportForm

router = Router()


async def msg_update(state: FSMContext, user_message: Message | None = None, with_ui_open: bool = True):
    app_state = AppState()
    data = await state.get_data()
    page = data.get("page", 1)
    bugs_list = await bugs_db.get_list(page)
    total_bugs = await bugs_db.get_total()
    msg = data.get("bugs_message", None)

    if msg:
        try:
            await msg.edit_text("Загрузка...")
        except TelegramBadRequest:
            msg = None
    if not msg and with_ui_open:
        msg = await app_state.bot.send_message(user_message.chat.id, "Загрузка...")
        await state.update_data(bugs_message=msg)

    if not bugs_list:
        if page > 1:
            return
        await user_message.answer("Известных багов нет!")
        await msg.delete()
        await state.clear()
        return

    not_solved_bugs = [i for i in bugs_list if not i.solved]
    bugs_buttons = [[] for i in range(ceil(len(not_solved_bugs) / app_state.config.BUTTONS_PAGE_LIMIT))]
    for num, i in enumerate(not_solved_bugs, 1):
        bugs_buttons[num // app_state.config.BUTTONS_PAGE_LIMIT].append(
            InlineKeyboardButton(text=f"[{i.id}] ✔️", callback_data=f"bug_solved:{i.id}:1")
        )

    paginator = [
        InlineKeyboardButton(text="Отмена", callback_data="bug_cancel"),
    ]
    if page > 1:
        paginator.insert(0, InlineKeyboardButton(text="<<<", callback_data="bugs_page:prev"))
    if total_bugs // (page * app_state.config.BUTTONS_PAGE_LIMIT):
        paginator.append(InlineKeyboardButton(text=">>>", callback_data="bugs_page:next"))
    if msg:
        await msg.edit_text(
            **Text(
                as_list(
                    Bold("Список известных багов:"),
                    *[
                        f"{"✅" if i.solved else "❗️"} {i.id}. [@{i.telegram_tag}] {i.description}\n"
                        for i in bugs_list
                    ]
                )
            ).as_kwargs(),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                *bugs_buttons,
                paginator
            ])
        )


@router.message(Command("bug"))
async def bug_report(message: types.Message, state: FSMContext):
    match message.chat.type:
        case ChatType.PRIVATE:
            await message.reply(
                "Опишите проблему. Разработчик сразу ее увидит (но не факт, что сразу же починит).",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Отмена", callback_data="bug_cancel")]
                ])
            )
        case _:
            return

    await state.set_state(BugFSM.bug_written)


@router.message(Command("bugs"))
async def bugs_report(message: types.Message, state: FSMContext):
    app_state = AppState()

    if message.from_user.id != app_state.config.DEV_TG_ID:
        return
    match message.chat.type:
        case ChatType.PRIVATE:
            await msg_update(state, message)
            await message.delete()
        case _:
            return


@router.message(BugFSM.bug_written)
async def fsm_bug_written(message: types.Message, state: FSMContext):
    app_state = AppState()
    await state.set_state(None)

    bug_id = await bugs_db.create(
        BugReportForm(
            telegram_id=message.from_user.id,
            telegram_tag=message.from_user.username,
            description=message.text,
        )
    )

    # Отсылка деву в личку нового бага
    await app_state.bot.send_message(
        app_state.config.DEV_TG_ID,
        text=f"{message.chat.full_name} (@{message.chat.username}): {message.text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✔️ Решено", callback_data=f"bug_solved:{bug_id}:0"),
                InlineKeyboardButton(text="Посмотрим", callback_data="bug_reviewed")
            ],

        ]),
        disable_notification=True
    )
    await msg_update(state, with_ui_open=False)

    await message.answer("Спасибо за Ваш баг-репорт. Помацаем шо там", reply_markup=None)


@router.callback_query(F.data.startswith("bugs_page"))
async def bugs_page(callback: CallbackQuery, state: FSMContext):
    cmd, val = callback.data.split(":", 2)
    data = await state.get_data()
    page = data.get("page", 1)
    match val:
        case "prev":
            page = max(page - 1, 1)
        case "next":
            page = page + 1

    await state.update_data(page=page)
    await msg_update(state, callback.message)


@router.callback_query(F.data.startswith("bug_solved"))
async def bug_solved(callback: CallbackQuery, state: FSMContext):
    cmd, val, with_ui_open = callback.data.split(":", 2)

    await bugs_db.update(val, solved=True)
    await callback.message.delete()
    await msg_update(state, callback.message, with_ui_open == "1")


@router.callback_query(F.data == "bug_cancel")
async def bug_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Баг-репорт отменен")


@router.callback_query(F.data == 'bug_reviewed')
async def bug_reviewed(callback: CallbackQuery):
    await callback.message.delete()
