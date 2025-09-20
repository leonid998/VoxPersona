import os
import logging
import asyncio
from pyrogram import Client, idle

# Import using SafeImporter for reliability
try:
    from import_utils import safe_import, with_recovery
    from error_recovery import recover_from_error
    
    # Use safe imports for critical modules
    config = safe_import('config', required=True)
    handlers = safe_import('handlers', required=True)
    run_analysis = safe_import('run_analysis', required=True)
    rag_persistence = safe_import('rag_persistence', required=True)
    storage = safe_import('storage', required=True)
    
    # Extract needed constants with fallbacks
    TELEGRAM_BOT_TOKEN = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    API_ID = getattr(config, 'API_ID', None)
    API_HASH = getattr(config, 'API_HASH', None)
    SESSION_NAME = getattr(config, 'SESSION_NAME', 'voxpersona')
    RAG_INDEX_DIR = getattr(config, 'RAG_INDEX_DIR', './rag_indices')
    
    # Get functions with fallbacks
    init_rags = getattr(run_analysis, 'init_rags', lambda: {})
    save_rag_indices = getattr(rag_persistence, 'save_rag_indices', lambda x: None)
    load_rag_indices = getattr(rag_persistence, 'load_rag_indices', lambda: {})
    safe_filename = getattr(storage, 'safe_filename', lambda x: x)
    
except ImportError as e:
    logging.warning(f"Using fallback imports due to import error: {e}")
    # Fallback to original imports
    from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SESSION_NAME, RAG_INDEX_DIR
    import handlers
    from run_analysis import init_rags
    from rag_persistence import save_rag_indices, load_rag_indices
    from storage import safe_filename
    
    # Create dummy recovery functions
    def with_recovery(context=None):
        def decorator(func):
            return func
        return decorator
    
    def recover_from_error(error, context=None):
        return None

import nest_asyncio
import sys

nest_asyncio.apply()


@with_recovery({'operation': 'periodic_save_rags'})
async def periodic_save_rags():
    while True:
        await asyncio.sleep(900)
        if hasattr(handlers, 'rags_lock'):
            async with handlers.rags_lock:
                try:
                    if hasattr(handlers, 'rags'):
                        save_rag_indices(handlers.rags)
                except Exception as e:
                    logging.warning("Не удалось сохранить RAG индексы: %s", e)
                    # Try recovery
                    recovery_result = recover_from_error(e, {
                        'operation': 'save_rag_indices',
                        'context': 'periodic_save'
                    })
                    if recovery_result:
                        logging.info("RAG сохранение восстановлено через recovery система")
        else:
            logging.warning("handlers.rags_lock не найден, пропускаем сохранение RAG")


@with_recovery({'operation': 'load_rags'})
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
            if hasattr(handlers, 'set_rags'):
                await handlers.set_rags(rags)
            current_rags = rags
        else:
            if hasattr(handlers, 'set_rags'):
                await handlers.set_rags(mapped_rags)
            current_rags = mapped_rags

        # Ensure RAG_INDEX_DIR exists and is accessible
        if os.path.exists(RAG_INDEX_DIR) and not os.listdir(RAG_INDEX_DIR):
            try:
                save_rag_indices(current_rags)
            except Exception as e:
                logging.warning("Не удалось сохранить RAG индексы: %s", e)
                # Try recovery
                recovery_result = recover_from_error(e, {
                    'operation': 'save_rag_indices',
                    'context': 'initial_save'
                })

        asyncio.create_task(periodic_save_rags())
        logging.info("RAG модели загружены")
    except Exception as e:
        logging.error(f"Ошибка при инициализации RAG моделей: {e}")
        # Try recovery
        recovery_result = recover_from_error(e, {
            'operation': 'load_rags',
            'context': 'initialization'
        })
        if recovery_result:
            logging.info("RAG инициализация восстановлена через recovery система")
        else:
            logging.warning("RAG recovery не удалась, продолжаем без RAG моделей")


@with_recovery({'operation': 'main_app_startup'})
async def main():
    # Validate required configuration
    if not all([TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
        error_msg = "Missing required configuration: TELEGRAM_BOT_TOKEN, API_ID, or API_HASH"
        logging.error(error_msg)
        
        # Try to recover configuration
        recovery_result = recover_from_error(
            ValueError(error_msg),
            {'operation': 'config_validation', 'missing_configs': ['TELEGRAM_BOT_TOKEN', 'API_ID', 'API_HASH']}
        )
        
        if not recovery_result:
            raise ValueError(error_msg)
    
    try:
        app = Client(
            SESSION_NAME,
            api_id=int(API_ID),
            api_hash=API_HASH,
            bot_token=TELEGRAM_BOT_TOKEN
        )

        if hasattr(handlers, 'register_handlers'):
            handlers.register_handlers(app)
        else:
            logging.warning("handlers.register_handlers не найден")

        await app.start()
        asyncio.create_task(load_rags())
        logging.info("Бот запущен. Ожидаю сообщений...")
        await idle()
        await app.stop()
        
    except Exception as e:
        logging.error(f"Ошибка запуска главного приложения: {e}")
        
        # Try recovery
        recovery_result = recover_from_error(e, {
            'operation': 'app_startup',
            'context': 'main_function'
        })
        
        if not recovery_result:
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Критическая ошибка приложения: {e}")
        
        # Try final recovery attempt
        recovery_result = recover_from_error(e, {
            'operation': 'application_crash',
            'context': 'main_entry_point'
        })
        
        if not recovery_result:
            logging.error("Приложения не может быть восстановлена. Завершение.")
            sys.exit(1)
# Тест автоматического деплоя - Tue Aug 26 08:56:17 EDT 2025
# Webhook test comment added at Tue Aug 26 08:56:17 EDT 2025
# Второй тест webhook деплоя - Tue Aug 26 08:57:57 EDT 2025
# ФИНАЛЬНЫЙ ТЕСТ WEBHOOK ДЕПЛОЯ - Tue Aug 26 08:59:44 EDT 2025
# ТЕСТ С ИСПРАВЛЕННЫМ WEBHOOK СЕРВЕРОМ - Tue Aug 26 09:02:41 EDT 2025
# ОКОНЧАТЕЛЬНЫЙ ТЕСТ АВТОДЕПЛОЯ - Tue Aug 26 09:05:12 EDT 2025
# УНИКАЛЬНЫЙ ТЕСТ АВТОДЕПЛОЯ ID:1756213698 - Tue Aug 26 09:08:18 EDT 2025
# ТЕСТ 1: APP-ONLY ДЕПЛОЙ - Tue Aug 26 01:28:11 PM UTC 2025
# ТЕСТ ИСПРАВЛЕННОЙ ЛОГИКИ 1: Python код - Tue Aug 26 01:37:16 PM UTC 2025
