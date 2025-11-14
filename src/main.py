import os
import logging
import asyncio
from pathlib import Path
from pyrogram import Client, idle
from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME, RAG_INDEX_DIR, set_auth_manager
import handlers
from run_analysis import init_rags
from rag_persistence import save_rag_indices, load_rag_indices
from storage import safe_filename
from auth_manager import AuthManager
import nest_asyncio

nest_asyncio.apply()

# ✅ ИСПРАВЛЕНИЕ: Установка уровня логирования INFO
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# ✅ ПРОБЛЕМА #2: Константа для минимального размера валидного индекса
MIN_VALID_INDEX_SIZE = 1_000_000  # 1MB - минимальный размер полного FAISS индекса


def should_save_indices(rags: dict) -> bool:
    """
    Проверяет, нужно ли сохранять индексы на диск.

    Логика:
    - Если индекса НЕТ на диске → сохранить
    - Если размер индекса < 1MB (неполный) → сохранить
    - Иначе → НЕ сохранять (индекс актуальный)

    Args:
        rags: Словарь RAG индексов

    Returns:
        bool: True если нужно сохранить, False иначе
    """
    for name in rags.keys():
        # Проверяем только FAISS индексы (у них есть метод save_local)
        if not hasattr(rags[name], "save_local"):
            continue

        # Путь к индексу на диске
        index_path = Path(RAG_INDEX_DIR) / safe_filename(name) / "index.faiss"

        # Если файла НЕТ → нужно сохранить
        if not index_path.exists():
            logging.debug(f"📝 Индекс '{name}': файл НЕ найден → сохранить")
            return True

        # ✅ ПРОБЛЕМА #1: Добавлена обработка OSError при stat()
        try:
            file_size = index_path.stat().st_size
        except OSError as e:
            logging.warning(f"⚠️ Индекс '{name}': ошибка чтения размера файла ({e}) → сохранить")
            return True

        # Если размер < 1MB (неполный) → нужно сохранить
        if file_size < MIN_VALID_INDEX_SIZE:
            logging.debug(f"📝 Индекс '{name}': размер < 1MB → сохранить")
            return True

    # Все индексы актуальны → НЕ сохранять
    logging.debug("✅ Все индексы актуальны → пропуск сохранения")
    return False


async def periodic_save_rags():
    """
    Периодически сохраняет RAG индексы на диск (каждые 15 минут).

    Логика:
    - Проверяем, нужно ли сохранять (через should_save_indices)
    - Сохраняем ТОЛЬКО если индексы изменились или отсутствуют
    - Логируем результат (сохранено или пропущено)
    """
    while True:
        await asyncio.sleep(900)  # 15 минут

        async with handlers.rags_lock:
            try:
                # ✅ Проверяем: нужно ли сохранять?
                if should_save_indices(handlers.rags):
                    save_rag_indices(handlers.rags)
                    logging.info("✅ RAG индексы сохранены на диск")
                else:
                    logging.debug("⏭️  Пропуск сохранения: индексы актуальны")
            except Exception as e:
                logging.warning(f"❌ Не удалось сохранить RAG индексы: {e}")



async def migrate_old_indices_if_needed():
    """
    Автоматическая миграция старых FAISS индексов при смене embeddings модели.

    Проверяет, существуют ли индексы с устаревшей моделью (all-MiniLM-L6-v2).
    Если да - удаляет их для принудительного пересоздания с новой моделью (BAAI/bge-m3).

    Критично: Запускается ДО load_rag_indices() в load_rags().

    Логика работы:
    1. Проверяет наличие маркера старой модели (.old_model_all-MiniLM-L6-v2)
    2. Проверяет наличие маркера новой модели (.model_BAAI_bge-m3)
    3. Если старая модель или нет новой → удаляет все .faiss и .pkl файлы
    4. Создает маркер новой модели для предотвращения повторной миграции
    """
    from pathlib import Path
    import shutil

    indices_dir = Path(RAG_INDEX_DIR)

    # Проверяем наличие маркеров модели
    old_model_marker = indices_dir / ".old_model_all-MiniLM-L6-v2"
    new_model_marker = indices_dir / ".model_BAAI_bge-m3"

    # Если есть маркер старой модели ИЛИ нет маркера новой модели → миграция нужна
    if old_model_marker.exists() or not new_model_marker.exists():
        logging.warning("⚠️ Обнаружены индексы с устаревшей embeddings моделью!")
        logging.info("🔄 Запуск автоматической миграции индексов...")

        # Удаляем все .faiss и .pkl файлы РЕКУРСИВНО из всех поддиректорий (старые индексы)
        for file_pattern in ["**/*.faiss", "**/*.pkl"]:  # Рекурсивное удаление из всех поддиректорий
            for old_file in indices_dir.glob(file_pattern):
                try:
                    old_file.unlink()
                    logging.info(f"   Удален старый индекс: {old_file}")
                except Exception as e:
                    logging.error(f"   Не удалось удалить {old_file}: {e}")

        # Удаляем старый маркер (если существует)
        if old_model_marker.exists():
            old_model_marker.unlink()

        # Создаем маркер новой модели
        new_model_marker.touch()
        logging.info("✅ Миграция завершена. Индексы будут пересозданы с моделью BAAI/bge-m3")
    else:
        logging.info("✅ Индексы используют актуальную модель BAAI/bge-m3")


async def load_rags():
    """Initialize RAG models without blocking the bot startup."""
    logging.info("Запуск фоновой инициализации RAG моделей")

    # Автоматическая миграция старых индексов перед загрузкой
    await migrate_old_indices_if_needed()

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
            # === НОВЫЕ ИНДЕКСЫ МИ (Маркетинговое исследование) ===
            "Отчеты по дизайну",
            "Отчеты по обследованию",
            "Итоговые отчеты",
            "Исходники дизайн",
            "Исходники обследование",
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


async def init_auth_manager():
    """
    Инициализация AuthManager при старте бота.

    Создает экземпляр AuthManager и устанавливает его как глобальный
    через config.set_auth_manager() для использования в handlers.

    Директория auth_data будет создана автоматически, если не существует.
    """
    try:
        # Определить путь к auth_data (рядом с main.py)
        auth_data_path = Path(__file__).parent / "auth_data"

        # Создать AuthManager
        auth_manager = AuthManager(base_path=auth_data_path)

        # Установить глобальный auth_manager в config
        set_auth_manager(auth_manager)

        logging.info(f"AuthManager инициализирован успешно (auth_data: {auth_data_path})")

    except Exception as e:
        logging.error(f"Ошибка при инициализации AuthManager: {e}")
        raise


async def main():
    # Определить путь для сохранения Telegram session файлов
    session_dir = Path("/app/telegram_sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / SESSION_NAME

    app = Client(
        str(session_path),  # Полный путь к .session файлу
        api_id=int(API_ID),
        api_hash=API_HASH,
        bot_token=TELEGRAM_BOT_TOKEN
    )

    # КРИТИЧНО: Инициализация AuthManager ДО регистрации handlers
    # auth_filter требует get_auth_manager() != None
    await init_auth_manager()

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
