# Arma Stat Counter Telegram Web App

Отдельное FastAPI-приложение для Telegram Web App. Использует тот же `config.ini`, `API_TOKEN` и `PSQL_PATH`, что и бот, поэтому работает с общей PostgreSQL-базой.

## Запуск

```bash
cd arma_stat_counter
uvicorn web_app.main:app --host 0.0.0.0 --port 8000 --reload
```

Для Telegram Web App нужен публичный HTTPS URL. Укажи его в переменной окружения `WEB_APP_URI` или замени значение по умолчанию в `core/settings.py` перед регистрацией кнопки у бота.

## Авторизация

API принимает Telegram `initData` из заголовка `Authorization: tma <initData>` и проверяет подпись через bot token. Отдельная база для сессий не нужна.

Для локальной отладки без Telegram можно задать `WEB_APP_DEV_TELEGRAM_ID=<telegram_id>`, тогда API примет пустой `initData` как этого пользователя.
