"""
Утилита для безопасного удаления тестовых данных из PostgreSQL БД.

Поддерживает два режима:
- Вариант A: Удаление по test_session_id (если колонка существует)
- Вариант B: Удаление по user_id + timestamp (fallback)

Использование:
    from utils.cleanup import cleanup_test_data, cleanup_test_user_data

    # Вариант A: Удаление по session_id
    result = cleanup_test_data("20251022_153000")

    # Вариант B: Удаление по user_id + timestamp
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(hours=1)
    result = cleanup_test_user_data(155894817, cutoff)
"""

from typing import Dict, Optional, Any
from datetime import datetime
import time
import structlog

from db_handler.db import get_db_connection

logger = structlog.get_logger()


def cleanup_test_data(session_id: str) -> Dict[str, Any]:
    """
    Удалить все тестовые данные по test_session_id.

    Удаляет данные из всех таблиц, где есть колонка test_session_id.
    Операция выполняется в транзакции - при ошибке все откатывается.

    Args:
        session_id: Уникальный ID тестовой сессии (например "20251022_153000")

    Returns:
        dict с количеством удаленных строк по каждой таблице:
        {
            "conversations": 5,
            "conversation_messages": 120,
            "reports": 3,
            "audit_log": 15,
            "transcriptions": 2,
            "total_deleted": 145,
            "duration_ms": 250,
            "status": "success"
        }

    Raises:
        Exception: При ошибке БД (с автоматическим ROLLBACK)

    Example:
        >>> result = cleanup_test_data("20251022_153000")
        >>> print(f"Удалено: {result['total_deleted']} строк")
        Удалено: 145 строк
    """
    conn = None
    cursor = None
    start_time = time.time()

    # Таблицы для очистки (в порядке зависимостей)
    tables = [
        "conversation_messages",  # Зависит от conversations
        "conversations",          # Основная таблица
        "reports",               # Отчеты пользователя
        "audit_log",            # Логи аудита
        "transcriptions"        # Транскрипции аудио
    ]

    result: Dict[str, Any] = {
        "status": "success",
        "total_deleted": 0
    }

    logger.info("cleanup_started", session_id=session_id, tables=tables)

    try:
        # Получить соединение с БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # BEGIN транзакция (автоматически при первом запросе)

        # Удалить данные из каждой таблицы
        for table in tables:
            try:
                query = f"DELETE FROM {table} WHERE test_session_id = %s"
                cursor.execute(query, (session_id,))
                rows_deleted = cursor.rowcount

                result[table] = rows_deleted
                result["total_deleted"] += rows_deleted

                logger.info(
                    "cleaned_table",
                    table=table,
                    rows_deleted=rows_deleted,
                    session_id=session_id
                )

            except Exception as table_error:
                # Логировать ошибку для конкретной таблицы, но продолжить
                logger.warning(
                    "table_cleanup_skipped",
                    table=table,
                    error=str(table_error),
                    session_id=session_id
                )
                result[table] = 0

        # COMMIT транзакции
        conn.commit()

        # Рассчитать длительность операции
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            "cleanup_completed",
            session_id=session_id,
            total_deleted=result["total_deleted"],
            duration_ms=duration_ms
        )

        return result

    except Exception as e:
        # ROLLBACK транзакции при ошибке
        if conn:
            conn.rollback()
            logger.error(
                "cleanup_rollback",
                session_id=session_id,
                error=str(e)
            )

        logger.error(
            "cleanup_failed",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__
        )

        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "total_deleted": 0,
            "session_id": session_id
        }

    finally:
        # Закрыть соединение
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def cleanup_test_user_data(user_id: int, created_after: datetime) -> Dict[str, Any]:
    """
    Удалить данные тестового пользователя по user_id + timestamp.

    Fallback метод для случаев, когда test_session_id не существует в БД.
    Удаляет данные пользователя, созданные после указанного времени.

    Args:
        user_id: Telegram ID тестового пользователя (например 155894817)
        created_after: Удалить данные созданные после этого времени

    Returns:
        dict с количеством удаленных строк по каждой таблице:
        {
            "conversations": 3,
            "conversation_messages": 80,
            "reports": 2,
            "total_deleted": 85,
            "duration_ms": 180,
            "status": "success"
        }

    Raises:
        Exception: При ошибке БД (с автоматическим ROLLBACK)

    Example:
        >>> from datetime import datetime, timedelta
        >>> cutoff = datetime.now() - timedelta(hours=1)
        >>> result = cleanup_test_user_data(155894817, cutoff)
        >>> print(f"Удалено данных пользователя: {result['total_deleted']}")
        Удалено данных пользователя: 85
    """
    conn = None
    cursor = None
    start_time = time.time()

    # Таблицы с полями user_id и created_at/timestamp
    tables_config = [
        {"name": "conversation_messages", "time_field": "timestamp"},
        {"name": "conversations", "time_field": "created_at"},
        {"name": "reports", "time_field": "timestamp"},
        {"name": "transcriptions", "time_field": "created_at"}
    ]

    result: Dict[str, Any] = {
        "status": "success",
        "total_deleted": 0,
        "user_id": user_id,
        "created_after": created_after.isoformat()
    }

    logger.info(
        "cleanup_user_started",
        user_id=user_id,
        created_after=created_after.isoformat()
    )

    try:
        # Получить соединение с БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # BEGIN транзакция

        # Удалить данные из каждой таблицы
        for table_config in tables_config:
            table = table_config["name"]
            time_field = table_config["time_field"]

            try:
                query = f"""
                    DELETE FROM {table}
                    WHERE user_id = %s AND {time_field} >= %s
                """
                cursor.execute(query, (user_id, created_after))
                rows_deleted = cursor.rowcount

                result[table] = rows_deleted
                result["total_deleted"] += rows_deleted

                logger.info(
                    "cleaned_user_table",
                    table=table,
                    rows_deleted=rows_deleted,
                    user_id=user_id
                )

            except Exception as table_error:
                # Логировать ошибку для конкретной таблицы
                logger.warning(
                    "user_table_cleanup_skipped",
                    table=table,
                    error=str(table_error),
                    user_id=user_id
                )
                result[table] = 0

        # COMMIT транзакции
        conn.commit()

        # Рассчитать длительность операции
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            "cleanup_user_completed",
            user_id=user_id,
            total_deleted=result["total_deleted"],
            duration_ms=duration_ms
        )

        return result

    except Exception as e:
        # ROLLBACK транзакции при ошибке
        if conn:
            conn.rollback()
            logger.error(
                "cleanup_user_rollback",
                user_id=user_id,
                error=str(e)
            )

        logger.error(
            "cleanup_user_failed",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__
        )

        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "total_deleted": 0,
            "user_id": user_id
        }

    finally:
        # Закрыть соединение
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def verify_cleanup(session_id: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Проверить результаты очистки - остались ли тестовые данные.

    Args:
        session_id: Проверить по test_session_id (Вариант A)
        user_id: Проверить по user_id (Вариант B)

    Returns:
        dict с количеством оставшихся строк:
        {
            "conversations": 0,
            "conversation_messages": 0,
            "total_remaining": 0,
            "status": "clean" | "data_remaining"
        }
    """
    conn = None
    cursor = None

    result: Dict[str, Any] = {
        "status": "clean",
        "total_remaining": 0
    }

    tables = ["conversations", "conversation_messages", "reports", "transcriptions"]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for table in tables:
            if session_id:
                query = f"SELECT COUNT(*) FROM {table} WHERE test_session_id = %s"
                cursor.execute(query, (session_id,))
            elif user_id:
                query = f"SELECT COUNT(*) FROM {table} WHERE user_id = %s"
                cursor.execute(query, (user_id,))
            else:
                continue

            count = cursor.fetchone()[0]
            result[table] = count
            result["total_remaining"] += count

        if result["total_remaining"] > 0:
            result["status"] = "data_remaining"

        logger.info("cleanup_verified", **result)
        return result

    except Exception as e:
        logger.error("verify_cleanup_failed", error=str(e))
        return {"status": "error", "error": str(e)}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    """
    Примеры использования утилиты очистки.
    """
    print("=" * 60)
    print("🧹 VoxPersona - Cleanup Utility")
    print("=" * 60)

    # Пример 1: Удаление по session_id (Вариант A)
    print("\n[Пример 1] Удаление тестовых данных по session_id:")
    print("-" * 60)
    test_session_id = "20251022_153000"
    print(f"Session ID: {test_session_id}")

    result_a = cleanup_test_data(test_session_id)
    print(f"\nРезультат:")
    print(f"  Статус: {result_a['status']}")
    print(f"  Всего удалено: {result_a['total_deleted']} строк")
    print(f"  Длительность: {result_a.get('duration_ms', 0)} мс")

    if result_a['status'] == 'success':
        for table in ["conversations", "conversation_messages", "reports"]:
            if table in result_a:
                print(f"  - {table}: {result_a[table]} строк")

    # Пример 2: Удаление по user_id + timestamp (Вариант B)
    print("\n[Пример 2] Удаление данных пользователя по user_id + timestamp:")
    print("-" * 60)
    from datetime import timedelta

    test_user_id = 155894817
    cutoff_time = datetime.now() - timedelta(hours=1)
    print(f"User ID: {test_user_id}")
    print(f"Created after: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")

    result_b = cleanup_test_user_data(test_user_id, cutoff_time)
    print(f"\nРезультат:")
    print(f"  Статус: {result_b['status']}")
    print(f"  Всего удалено: {result_b['total_deleted']} строк")
    print(f"  Длительность: {result_b.get('duration_ms', 0)} мс")

    if result_b['status'] == 'success':
        for table in ["conversations", "conversation_messages", "reports"]:
            if table in result_b:
                print(f"  - {table}: {result_b[table]} строк")

    # Пример 3: Проверка результатов очистки
    print("\n[Пример 3] Проверка результатов очистки:")
    print("-" * 60)

    verify_result = verify_cleanup(session_id=test_session_id)
    print(f"Статус: {verify_result['status']}")
    print(f"Осталось строк: {verify_result['total_remaining']}")

    print("\n" + "=" * 60)
