import logging
import asyncio
from pyrogram import Client, idle
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME
from handlers import register_handlers, set_rags
from run_analysis import init_rags
import nest_asyncio

nest_asyncio.apply()


async def load_rags():
    """Initialize RAG models without blocking the bot startup."""
    logging.info("Запуск фоновой инициализации RAG моделей")
    try:
        rags = await asyncio.to_thread(init_rags)
        set_rags(rags)
        logging.info("RAG модели загружены")
    except Exception as e:
        logging.error(f"Ошибка при инициализации RAG моделей: {e}")


async def main():
    app = Client(
        SESSION_NAME,
        api_id=int(API_ID),
        api_hash=API_HASH,
        bot_token=TELEGRAM_BOT_TOKEN
    )

    register_handlers(app)

    await app.start()
    asyncio.create_task(load_rags())
    logging.info("Бот запущен. Ожидаю сообщений...")
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
# Тест автоматического деплоя - Tue Aug 26 08:56:17 EDT 2025
# Webhook test comment added at Tue Aug 26 08:56:17 EDT 2025
# Второй тест webhook деплоя - Tue Aug 26 08:57:57 EDT 2025
# ФИНАЛЬНЫЙ ТЕСТ WEBHOOK ДЕПЛОЯ - Tue Aug 26 08:59:44 EDT 2025
# ТЕСТ С ИСПРАВЛЕННЫМ WEBHOOK СЕРВЕРОМ - Tue Aug 26 09:02:41 EDT 2025
# ОКОНЧАТЕЛЬНЫЙ ТЕСТ АВТОДЕПЛОЯ - Tue Aug 26 09:05:12 EDT 2025
# УНИКАЛЬНЫЙ ТЕСТ АВТОДЕПЛОЯ ID:1756213698 - Tue Aug 26 09:08:18 EDT 2025
# ТЕСТ 1: APP-ONLY ДЕПЛОЙ - Tue Aug 26 01:28:11 PM UTC 2025
# ТЕСТ ИСПРАВЛЕННОЙ ЛОГИКИ 1: Python код - Tue Aug 26 01:37:16 PM UTC 2025
