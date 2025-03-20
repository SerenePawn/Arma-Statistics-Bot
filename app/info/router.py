from aiogram import types, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.formatting import Pre, Bold, as_list

from core.app_state import AppState
from logic.players import db as players_db
from logic.squads import db as squads_db

router = Router()


@router.message(F.chat.type.in_({"private"}), CommandStart())
async def start_behavior(message: types.Message):
    await message.reply(
            f"Привет, {message.from_user.full_name}.\n"
            "Если не работает что-либо, проверьте, может ли бот прислать Вам сообщение.\n\n"
            "Чтобы получить килл-лог других отрядов, "
            "введите в канал отряда с ботом простое название (без кавычек и прочих знаков). "
            "Например, `!tvt1 re` или `!if re`.\n"
            "Чтобы получить килл-лог за прошлые игры, введите название отряда как выше, но с `<-><кол-во игр>` "
            "(`-` ни на что не влияет)."
            "Например, `!tvt1 re 1` - получить за килл-лог отряда RE за позапрошлую игру TVT1, "
            "`!tvt2 re -2` - за 2 игры до последней игры TVT2, и т.д.\n"
            "Функционал получения килл-логов за игру пока реализован только для А3\n\n"
            
            "Получить список игроков в отряде - введите в личку (cюда): /players.\n"
            "Чтобы получить список игроков другого отряда, введите, например /players re.\n\n"
            
            "Если Вы нашли баг или имеется идея по улучшению, сообщите, пожалуйста, сюда через: /bug. "
            "Опишите баг как можно подробнее, пожалуйста, чтобы я мог его повторить и починить.\n"
            "А если интересно, что планируется еще в боте: /road_map\n\n"
            
            "КАК РАБОТАЕТ РАСПИСАНИЕ:\n"
            "Есть расписание отрядное: Админ группы проставил даты игр (напр. ТВТ1 в ЧТ в 20:00) "
            "и в 12:00 по МСК придет всем, кто не проставил свое личное расписание, уведомление об играх\n"
            "Есть расписание личное: Вы ставите, в какие дни будете приходить, и в какие не будете. "
            "В те дни, что Вы не проставили, Вам придет уведомление об играх.\n"
            "Есть расписание на неделю: Это расписание конкретно на текущую неделю, "
            "и только на этой неделе будет действовать. "
            "Уведомление не придет, только на следующей неделе (если не проставлено личное расписание.\n\n"
            
            "ДЛЯ АДМИНОВ/ГЛАВ ОТРЯДОВ:\n"
            "Бот рассчитан под использование внутри темы группы, хоть и может работать в группе без тем\n"
            "Для того, чтобы внедрить бота в свою группу, "
            "просто добавь бота, выдай права админа на удаление сообщений "
            "и пропиши в нужной теме группы /start_asb .\n"
            "Не забудь настроить бота через /admin_asb "
            "(расписание игр, например, или можно подправить тэги или имя отряда), "
            "после того как добавил и стартанул бота. \n\n"
        )


@router.message(F.chat.type.in_({"private"}), Command("road_map"))
async def start_behavior_asb(message: types.Message):
    await message.reply(
        "Список, что планируется, или уже, или скоро будет в работе:\n"
        " > График фрагов\n"
        " > Статистика фрагов отряда за неделю/месяц/год\n"
        " > Статистика фрагов отряда за неделю/месяц/год по сравнению с другими отрядами\n"
        # " > Друзья отряда\n"
        " > Поддержка рефоржера/А4 "
        "(По сути, мне нужны файлы окапа и их расшифровка. Если она совпадает с А3, то проблем ноль)\n"
        " > Поддержка остальных игр "
        "(Тут проблема в том, что нужно будет вырубать некоторые функции совсем, "
        "и обновлять функционал под возможность использовать его с разными играми. Тогда остается только "
        "функционал посещений. Если будет спрос, возьмусь, но есть ощущение, что никому это не всралось)) )\n"
    )


@router.message(F.chat.type.in_({"private"}), Command("how_to_play"))
async def how_to_play(message: types.Message):
    await message.reply(
        **Pre(
            "Главный источник информации, ссылок, а так же, "
            "где перед началом игр прочитать правила: https://www.red-bear.ru/index/pravila/0-31\n\n"
            "Как начать играть:\n"
            "1. Качаем сборку модов, сначала из воркшопа:\n"
            "   1.1. https://steamcommunity.com/sharedfiles/filedetails/?id=843425103\n"
            "   1.2. https://steamcommunity.com/sharedfiles/filedetails/?id=843577117\n"
            "   1.3. https://steamcommunity.com/sharedfiles/filedetails/?id=843593391\n"
            "   1.4. https://steamcommunity.com/sharedfiles/filedetails/?id=843632231\n"
            "   1.5. https://steamcommunity.com/sharedfiles/filedetails/?id=583496184\n"
            "   1.6. https://steamcommunity.com/sharedfiles/filedetails/?id=583544987\n\n"
            "2. Качаем Arma3Sync (https://disk.yandex.com/d/WAkLOuw0D38wdQ)\n"
            "   ИЛИ ResilioSync (https://download-cdn.resilio.com/stable/windows64/Resilio-Sync_x64.exe)\n"
            "3. Для Arma3Sync: заходим во вкладку 'Repositories', жмем '+', "
            "   вставляем ссылку автоконфига (дам ниже) и жмем 'Import', затем 'ОК'.\n"
            "   Для Resilio: Ебитесь сами.\n"
            "   Моды ставятся в корневую папку игры, по итогу в папке игры должны находиться папки (моды):\n"
            "      '@3CB_BAF_Full'\n"
            "      '@BW_Full'\n"
            "      '@RBCCore'\n"
            "      '@RBCMaps'\n"
            "      '@RBCMods'\n"
            "   Всего должно быть загружено модов: 11\n"
            "   Ссылки:\n"
            "      Автоконфиг основной (не будет работать во время игр): "
            "ftp://game.red-bear.ru/rbc_tvt/.a3s/autoconfig\n"
            "      Автоконфиг резервный: "
            "ftp://stels-repo.red-bear.ru/rbc_tvt/.a3s/autoconfig\n\n"
            "4. Качаем TeamSpeak (https://www.teamspeak.com/en/downloads/#ts3client) ИМЕННО 3-й Версии (3.6.х).\n\n"
            "5. Качаем плагин рации для TeamSpeak (https://disk.yandex.com/d/IaHcOu_GjZnQLQ).\n"
            "Устанавливается просто двойным кликом. Если вдруг спрашивает чем открыть, "
            "идем в папку с TeamSpeak и открываем при помощи 'package_inst.exe'.\n\n"
            "6. В TeamSpeak ищем сверху вкладку 'Инструменты' -> 'Параметры' -> 'Уведомления', "
            "ставим (слева) пакет звуков 'Sounds deactivated'. Перезапускаем TeamSpeak.\n\n"
            "7. Подключаемся на сервер Red Bear (ts.red-bear.ru) с паролем (bear123).\n\n",
            Bold("8. В ТЕЛЕГРАММЕ RED BEAR НЕ ЗАБЫВАЕМ ЗАПРОСИТЬ ВАЙТ-ЛИСТ, "
                 "ЕСЛИ РАННЕЕ НЕ ИГРАЛИ, ИНАЧЕ НЕ ЗАЙДЕТЕ.\n\n")
        ).as_kwargs()
    )


@router.message(F.chat.type.in_({"private"}), Command("players"))
async def get_squad_players(message: types.Message):
    app_state = AppState()
    cmd, *args = message.text.split(" ")
    if args:
        tag, *_ = args
        squad = await squads_db.get_by_tag(app_state.conn, tag)
        if not squad:
            await message.reply(
                "Не найдено указанного отряда."
            )
            return
        squad_players = await players_db.get_by_squad_id(app_state.conn, squad.id)
    else:
        player = await players_db.get_by_tg_id(app_state.conn, message.from_user.id)
        if not player:
            await message.reply(
                "Вы не зарегистрированы ни в одном отряде. "
                "Напишите клан-тэг (`/player re`, например) или зарегистрируйтесь в отряде."
            )
            return
        squad = await squads_db.get(app_state.conn, player.squad_id)
        squad_players = await players_db.get_by_squad_id(app_state.conn, squad.id)

    await app_state.bot.send_message(
        chat_id=message.from_user.id,
        **as_list(
            Bold("⭐️ ", squad.name),
            f"Тэги отряда: {", ".join(squad.tags)}\n",
            *[
                f"🪖 [@{squad_player.telegram_tag}] {squad_player.name}" for squad_player in squad_players
            ]
        ).as_kwargs()
    )
