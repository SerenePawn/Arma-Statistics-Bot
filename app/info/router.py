from aiogram import types, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.formatting import Pre, Bold

router = Router()


@router.message(F.chat.type.in_({"private"}), CommandStart())
async def start_behavior(message: types.Message):
    await message.reply(
            f"Привет, {message.from_user.full_name}.\n"
            "Вы можете запустить приложение нажав на кнопку \"Открыть\" в списке чатов."
            "Если вы хотите использовать бота для своего отряда, пригласите его в чат отряда и напишите \"/start_asb\""
            
            "Если не работает что-либо, проверьте, может ли бот прислать Вам сообщение.\n\n"

            "Если Вы нашли баг или имеется идея по улучшению, сообщите, пожалуйста, сюда через: /bug. "
            "Опишите баг как можно подробнее, пожалуйста, чтобы я мог его повторить и починить.\n"
            "А если интересно, что планируется еще в боте: /road_map\n\n"
        )


@router.message(F.chat.type.in_({"private"}), Command("road_map"))
async def start_behavior_asb(message: types.Message):
    await message.reply(
        "Список, что планируется, или скоро будет в работе:\n"
        " > Расшифровка файлов (окапов) WOG\n"
        " > Статистика фрагов отряда за неделю/месяц/год\n"
        " > Статистика фрагов отряда за неделю/месяц/год по сравнению с другими отрядами\n"
        " > Поддержка рефоржера/А4 "
    )


@router.message(F.chat.type.in_({"private"}), Command("how_to_play"))
async def how_to_play(message: types.Message):
    await message.reply(
        **Pre(
            "А НИКАК НАХУЙ! ЧЕРЕЗ БОЛЬ И СТРАДАНИЯ!"
        ).as_kwargs()
    )
