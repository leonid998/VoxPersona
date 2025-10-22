"""
Утилита для безопасного удаления тестовых данных из файловой системы.

Menu Crawler не создаёт данные в БД, только на файловой системе.
Cleanup проверяет conversations/ и md_reports/ на наличие тестовых файлов.

Использование:
    from utils.cleanup import cleanup_test_files, verify_cleanup_files

    # Удалить файлы тестового пользователя
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(hours=1)
    result = cleanup_test_files(155894817, cutoff)

    # Проверить результаты
    verify_result = verify_cleanup_files(155894817)
"""

import os
import json
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
import time
import structlog

logger = structlog.get_logger()


def cleanup_test_files(user_id: int, created_after: datetime, base_path: str = "/home/voxpersona_user/VoxPersona") -> Dict[str, Any]:
    """
    Удалить файлы тестового пользователя созданные после указанного времени.

    Это safety net (3й уровень защиты) на случай, если TEST_USER_ID
    защита в handlers.py не сработала и Menu Crawler создал файлы.

    Ожидаемый результат: 0 файлов удалено (доказывает, что защита работает!)

    Args:
        user_id: Telegram ID тестового пользователя (например 155894817)
        created_after: Удалить файлы созданные после этого времени
        base_path: Корневая директория VoxPersona

    Returns:
        dict с количеством удалённых файлов:
        {
            "conversations_deleted": 0,
            "reports_deleted": 0,
            "total_deleted": 0,
            "duration_ms": 50,
            "status": "success"
        }

    Example:
        >>> from datetime import datetime, timedelta
        >>> cutoff = datetime.now() - timedelta(hours=1)
        >>> result = cleanup_test_files(155894817, cutoff)
        >>> print(f"Удалено файлов: {result['total_deleted']}")
        Удалено файлов: 0  # Ожидаемый результат!
    """
    start_time = time.time()

    result: Dict[str, Any] = {
        "status": "success",
        "conversations_deleted": 0,
        "reports_deleted": 0,
        "total_deleted": 0,
        "user_id": user_id,
        "created_after": created_after.isoformat(),
        "deleted_files": []
    }

    logger.info(
        "cleanup_files_started",
        user_id=user_id,
        created_after=created_after.isoformat(),
        base_path=base_path
    )

    try:
        # Конвертировать created_after в timestamp для сравнения
        cutoff_timestamp = created_after.timestamp()

        # 1. Проверить conversations/user_{user_id}/
        conversations_dir = Path(base_path) / "conversations" / f"user_{user_id}"
        if conversations_dir.exists():
            logger.info("checking_conversations", path=str(conversations_dir))

            for file_path in conversations_dir.glob("*.json"):
                try:
                    # Получить время модификации файла
                    file_mtime = file_path.stat().st_mtime

                    if file_mtime >= cutoff_timestamp:
                        # Файл создан после cutoff - удалить
                        file_path.unlink()
                        result["conversations_deleted"] += 1
                        result["deleted_files"].append(str(file_path))

                        logger.info(
                            "file_deleted",
                            file=str(file_path),
                            mtime=datetime.fromtimestamp(file_mtime).isoformat()
                        )

                except Exception as file_error:
                    logger.warning(
                        "file_delete_failed",
                        file=str(file_path),
                        error=str(file_error)
                    )

        # 2. Проверить md_reports/user_{user_id}/
        reports_dir = Path(base_path) / "md_reports" / f"user_{user_id}"
        if reports_dir.exists():
            logger.info("checking_reports", path=str(reports_dir))

            for file_path in reports_dir.glob("*"):
                try:
                    # Пропустить директории
                    if file_path.is_dir():
                        continue

                    # Получить время модификации файла
                    file_mtime = file_path.stat().st_mtime

                    if file_mtime >= cutoff_timestamp:
                        # Файл создан после cutoff - удалить
                        file_path.unlink()
                        result["reports_deleted"] += 1
                        result["deleted_files"].append(str(file_path))

                        logger.info(
                            "file_deleted",
                            file=str(file_path),
                            mtime=datetime.fromtimestamp(file_mtime).isoformat()
                        )

                except Exception as file_error:
                    logger.warning(
                        "file_delete_failed",
                        file=str(file_path),
                        error=str(file_error)
                    )

        # Подсчитать итоги
        result["total_deleted"] = result["conversations_deleted"] + result["reports_deleted"]

        # Рассчитать длительность
        duration_ms = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            "cleanup_files_completed",
            user_id=user_id,
            conversations_deleted=result["conversations_deleted"],
            reports_deleted=result["reports_deleted"],
            total_deleted=result["total_deleted"],
            duration_ms=duration_ms
        )

        # Если ничего не удалено - это ХОРОШО! Защита работает
        if result["total_deleted"] == 0:
            logger.info(
                "cleanup_success_no_files",
                message="✅ Защита TEST_USER_ID работает! Тестовые файлы не были созданы."
            )

        return result

    except Exception as e:
        logger.error(
            "cleanup_files_failed",
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


def verify_cleanup_files(user_id: int, base_path: str = "/home/voxpersona_user/VoxPersona") -> Dict[str, Any]:
    """
    Проверить наличие тестовых файлов после cleanup.

    Args:
        user_id: Telegram ID тестового пользователя
        base_path: Корневая директория VoxPersona

    Returns:
        dict с количеством оставшихся файлов:
        {
            "conversations_remaining": 5,
            "reports_remaining": 10,
            "total_remaining": 15,
            "status": "data_remaining" | "clean"
        }
    """
    result: Dict[str, Any] = {
        "status": "clean",
        "conversations_remaining": 0,
        "reports_remaining": 0,
        "total_remaining": 0,
        "user_id": user_id
    }

    logger.info("verify_cleanup_started", user_id=user_id)

    try:
        # Проверить conversations/user_{user_id}/
        conversations_dir = Path(base_path) / "conversations" / f"user_{user_id}"
        if conversations_dir.exists():
            conversations_files = list(conversations_dir.glob("*.json"))
            result["conversations_remaining"] = len(conversations_files)

        # Проверить md_reports/user_{user_id}/
        reports_dir = Path(base_path) / "md_reports" / f"user_{user_id}"
        if reports_dir.exists():
            reports_files = [f for f in reports_dir.iterdir() if f.is_file()]
            result["reports_remaining"] = len(reports_files)

        # Подсчитать итоги
        result["total_remaining"] = result["conversations_remaining"] + result["reports_remaining"]

        if result["total_remaining"] > 0:
            result["status"] = "data_remaining"
            logger.warning(
                "cleanup_incomplete",
                conversations_remaining=result["conversations_remaining"],
                reports_remaining=result["reports_remaining"],
                total_remaining=result["total_remaining"]
            )
        else:
            logger.info("cleanup_verified_clean", message="✅ Нет оставшихся тестовых файлов")

        return result

    except Exception as e:
        logger.error("verify_cleanup_failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "user_id": user_id
        }


def get_test_files_info(user_id: int, base_path: str = "/home/voxpersona_user/VoxPersona") -> Dict[str, Any]:
    """
    Получить информацию о тестовых файлах без удаления.

    Полезно для диагностики - показывает какие файлы есть у тестового пользователя.

    Args:
        user_id: Telegram ID тестового пользователя
        base_path: Корневая директория VoxPersona

    Returns:
        dict с информацией о файлах:
        {
            "conversations": [
                {"file": "uuid.json", "size": 1024, "mtime": "2025-10-22T15:30:00"}
            ],
            "reports": [
                {"file": "report.md", "size": 2048, "mtime": "2025-10-22T16:00:00"}
            ],
            "total_files": 2,
            "total_size_bytes": 3072
        }
    """
    result: Dict[str, Any] = {
        "user_id": user_id,
        "conversations": [],
        "reports": [],
        "total_files": 0,
        "total_size_bytes": 0
    }

    try:
        # Conversations
        conversations_dir = Path(base_path) / "conversations" / f"user_{user_id}"
        if conversations_dir.exists():
            for file_path in conversations_dir.glob("*.json"):
                stat = file_path.stat()
                result["conversations"].append({
                    "file": file_path.name,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
                result["total_size_bytes"] += stat.st_size

        # Reports
        reports_dir = Path(base_path) / "md_reports" / f"user_{user_id}"
        if reports_dir.exists():
            for file_path in reports_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    result["reports"].append({
                        "file": file_path.name,
                        "size": stat.st_size,
                        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    result["total_size_bytes"] += stat.st_size

        result["total_files"] = len(result["conversations"]) + len(result["reports"])

        logger.info(
            "test_files_info",
            user_id=user_id,
            total_files=result["total_files"],
            total_size_bytes=result["total_size_bytes"]
        )

        return result

    except Exception as e:
        logger.error("get_test_files_info_failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "user_id": user_id
        }


if __name__ == "__main__":
    """
    Примеры использования утилиты очистки файлов.
    """
    print("=" * 60)
    print("🧹 VoxPersona Menu Crawler - Cleanup Utility")
    print("=" * 60)

    test_user_id = 155894817

    # Пример 1: Получить информацию о файлах
    print("\n[Пример 1] Информация о тестовых файлах:")
    print("-" * 60)

    # Для локального тестирования используем относительный путь
    base_path = "."

    info = get_test_files_info(test_user_id, base_path)
    print(f"User ID: {test_user_id}")
    print(f"Всего файлов: {info.get('total_files', 0)}")
    print(f"Размер: {info.get('total_size_bytes', 0)} байт")

    if info.get('conversations'):
        print(f"\nConversations: {len(info['conversations'])}")
        for conv in info['conversations'][:3]:  # Показать первые 3
            print(f"  - {conv['file']} ({conv['size']} байт)")

    if info.get('reports'):
        print(f"\nReports: {len(info['reports'])}")
        for report in info['reports'][:3]:  # Показать первые 3
            print(f"  - {report['file']} ({report['size']} байт)")

    # Пример 2: Удалить файлы созданные за последний час
    print("\n[Пример 2] Удаление тестовых файлов (созданных за последний час):")
    print("-" * 60)
    from datetime import timedelta

    cutoff_time = datetime.now() - timedelta(hours=1)
    print(f"User ID: {test_user_id}")
    print(f"Created after: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")

    result = cleanup_test_files(test_user_id, cutoff_time, base_path)
    print(f"\nРезультат:")
    print(f"  Статус: {result['status']}")
    print(f"  Conversations удалено: {result['conversations_deleted']}")
    print(f"  Reports удалено: {result['reports_deleted']}")
    print(f"  Всего удалено: {result['total_deleted']}")
    print(f"  Длительность: {result.get('duration_ms', 0)} мс")

    if result['total_deleted'] == 0:
        print("\n  ✅ ОТЛИЧНО! Тестовые файлы не были созданы.")
        print("  Это доказывает, что TEST_USER_ID защита работает корректно!")

    # Пример 3: Проверка результатов
    print("\n[Пример 3] Проверка результатов cleanup:")
    print("-" * 60)

    verify_result = verify_cleanup_files(test_user_id, base_path)
    print(f"Статус: {verify_result['status']}")
    print(f"Conversations осталось: {verify_result['conversations_remaining']}")
    print(f"Reports осталось: {verify_result['reports_remaining']}")
    print(f"Всего осталось: {verify_result['total_remaining']}")

    if verify_result['status'] == 'clean':
        print("\n✅ Cleanup прошел успешно - нет оставшихся файлов!")

    print("\n" + "=" * 60)
