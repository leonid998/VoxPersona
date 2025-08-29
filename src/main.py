import logging
import asyncio
import os
from pyrogram import Client, idle
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME, RAG_INDEX_DIR
from handlers import register_handlers, set_rags, get_rags
from run_analysis import init_rags
import nest_asyncio

nest_asyncio.apply()


async def load_rags():
    """Initialize RAG models without blocking the bot startup."""
    logging.info("Запуск фоновой инициализации RAG моделей")
    try:
        rags = await asyncio.to_thread(init_rags)
        set_rags(rags)
        save_rags_to_disk(rags)
        logging.info("RAG модели загружены")
    except Exception as e:
        logging.error(f"Ошибка при инициализации RAG моделей: {e}")


def save_rags_to_disk(rags: dict) -> None:
    """Persist FAISS indexes to disk."""
    for name, rag in rags.items():
        if hasattr(rag, "save_local"):
            path = os.path.join(RAG_INDEX_DIR, name)
            os.makedirs(path, exist_ok=True)
            rag.save_local(path)
    logging.info("RAG индексы сохранены на диск")


async def periodic_save_rags(interval: int = 900) -> None:
    """Save RAG indexes every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        current = get_rags()
        if not current:
            logging.info("RAG модели еще не загружены, пропускаю сохранение")
            continue
        try:
            save_rags_to_disk(current)
        except Exception as e:
            logging.error(f"Ошибка при сохранении RAG моделей: {e}")


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
    asyncio.create_task(periodic_save_rags())
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
