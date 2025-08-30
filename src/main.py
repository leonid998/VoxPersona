import os
import logging
import asyncio
from pyrogram import Client, idle
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME, RAG_INDEX_DIR
import handlers
from run_analysis import init_rags
from rag_persistence import save_rag_indices, load_rag_indices
from storage import safe_filename
import nest_asyncio

nest_asyncio.apply()


async def periodic_save_rags():
    while True:
        await asyncio.sleep(900)
        async with handlers.rags_lock:
            try:
                save_rag_indices(handlers.rags)
            except Exception as e:
                logging.warning("Не удалось сохранить RAG индексы: %s", e)


async def load_rags():
    """Initialize RAG models without blocking the bot startup."""
    logging.info("Запуск фоновой инициализации RAG моделей")
    try:
        loaded_rags = await asyncio.to_thread(load_rag_indices)

        expected_names = [
            "Интервью",
            "Дизайн",
            "Оценка методологии интервью",
            "Отчет о связках",
            "Общие факторы",
            "Факторы в этом заведении",
            "Оценка методологии аудита",
            "Соответствие программе аудита",
            "Структурированный отчет аудита",
        ]

        safe_map = {safe_filename(name): name for name in expected_names}
        mapped_rags = {safe_map.get(n, n): idx for n, idx in loaded_rags.items()}

        missing = [name for name in expected_names if name not in mapped_rags]

        if missing:
            rags = await asyncio.to_thread(init_rags, mapped_rags)
            await handlers.set_rags(rags)
            current_rags = rags
        else:
            await handlers.set_rags(mapped_rags)
            current_rags = mapped_rags

        if not os.listdir(RAG_INDEX_DIR):
            try:
                save_rag_indices(current_rags)
            except Exception as e:
                logging.warning("Не удалось сохранить RAG индексы: %s", e)

        asyncio.create_task(periodic_save_rags())
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

    handlers.register_handlers(app)

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
