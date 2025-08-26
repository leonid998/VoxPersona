import logging
from pyrogram import Client
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME
from handlers import register_handlers
import nest_asyncio

nest_asyncio.apply()

if __name__ == "__main__":
    app = Client(
        SESSION_NAME,
        api_id=int(API_ID),
        api_hash=API_HASH,
        bot_token=TELEGRAM_BOT_TOKEN
    )
    logging.info("Бот запущен. Ожидаю сообщений...")

    # Подключаем все обработчики
    register_handlers(app)

    # Запуск бота
    app.run()
# Тест автоматического деплоя - Tue Aug 26 08:56:17 EDT 2025
# Webhook test comment added at Tue Aug 26 08:56:17 EDT 2025
# Второй тест webhook деплоя - Tue Aug 26 08:57:57 EDT 2025
# ФИНАЛЬНЫЙ ТЕСТ WEBHOOK ДЕПЛОЯ - Tue Aug 26 08:59:44 EDT 2025
# ТЕСТ С ИСПРАВЛЕННЫМ WEBHOOK СЕРВЕРОМ - Tue Aug 26 09:02:41 EDT 2025
