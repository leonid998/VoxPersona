"""
Скрипт отправки временных паролей пользователям через Telegram.

Отправляет временные пароли мигрированным пользователям в личные сообщения
на основе migration_report.json, созданного скриптом migrate_users.py.

Логика отправки:
1. Чтение migration_report.json с telegram_id и temp_password
2. Отправка личного сообщения каждому пользователю через Telegram Bot
3. Rate limiting: 1 секунда задержки между отправками
4. Error handling: UserIsBlocked, PeerIdInvalid, FloodWait
5. Retry: до 3 раз с exponential backoff (1s → 2s → 4s)
6. Создание password_delivery_report.json с результатами

Безопасность:
- Отправка только в ЛИЧНЫЕ сообщения (не в группы)
- Логирование без паролей (только успех/ошибка)
- Предложение удалить migration_report.json после успешной отправки

Автор: backend-developer
Дата: 20 октября 2025
Задача: T19 (#00005_20251014_HRYHG)
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Добавить путь к src для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyrogram import Client
from pyrogram.errors import (
    UserIsBlocked,
    PeerIdInvalid,
    FloodWait,
    RPCError
)
from config import API_ID, API_HASH, TELEGRAM_BOT_TOKEN, SESSION_NAME

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class PasswordDeliveryService:
    """
    Сервис доставки паролей пользователям через Telegram.

    Attributes:
        client: Pyrogram Client для отправки сообщений
        sent_users: Список успешно обработанных пользователей
        failed_users: Список пользователей с ошибками доставки
    """

    def __init__(self, pyrogram_client: Client):
        """
        Инициализация сервиса доставки паролей.

        Args:
            pyrogram_client: Pyrogram Client (bot) для отправки сообщений
        """
        self.client = pyrogram_client
        self.sent_users: List[Dict] = []
        self.failed_users: List[Dict] = []

        logger.info("PasswordDeliveryService инициализирован")

    def _format_password_message(self, temp_password: str, expires_at: datetime) -> str:
        """
        Форматирует сообщение с временным паролем для пользователя.

        Args:
            temp_password: Временный пароль
            expires_at: Дата истечения пароля

        Returns:
            str: Отформатированное сообщение в Markdown
        """
        # Форматирование даты истечения (пример: "23 октября 2025, 14:32")
        months_ru = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]

        expires_formatted = f"{expires_at.day} {months_ru[expires_at.month - 1]} {expires_at.year}, {expires_at.strftime('%H:%M')}"

        message = f"""🔐 **Ваш временный пароль для входа в VoxPersona**

**Пароль:** `{temp_password}`

⚠️ **ВАЖНО:**
• Этот пароль действителен до **{expires_formatted}**
• При первом входе потребуется **сменить пароль**
• **Никому не сообщайте** пароль

Для входа отправьте команду /start и введите этот пароль при запросе."""

        return message

    async def _send_password_with_retry(
        self,
        telegram_id: int,
        username: str,
        temp_password: str,
        max_retries: int = 3
    ) -> Dict:
        """
        Отправляет пароль с retry mechanism при ошибках.

        Retry логика:
        - Попытка 1: без задержки
        - Попытка 2: задержка 1 секунда
        - Попытка 3: задержка 2 секунды
        - Попытка 4: задержка 4 секунды (exponential backoff)

        Args:
            telegram_id: Telegram ID пользователя
            username: Имя пользователя
            temp_password: Временный пароль
            max_retries: Максимальное количество попыток (по умолчанию 3)

        Returns:
            dict: Результат отправки с полями:
                - telegram_id: int
                - username: str
                - status: str ("success" или "failed")
                - error: str (только при ошибке)
        """
        # Вычислить дату истечения (3 дня от текущего момента)
        expires_at = datetime.now() + timedelta(days=3)

        # Форматировать сообщение
        message = self._format_password_message(temp_password, expires_at)

        # Попытки отправки с retry
        for attempt in range(max_retries + 1):
            try:
                # Отправить сообщение через bot
                await self.client.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode="Markdown"
                )

                logger.info(
                    f"✅ Пароль успешно отправлен: {username} (ID: {telegram_id})"
                )

                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "status": "success"
                }

            except UserIsBlocked:
                # Пользователь заблокировал бота → пропустить без retry
                logger.warning(
                    f"❌ Пользователь заблокировал бота: {username} (ID: {telegram_id})"
                )
                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "status": "failed",
                    "error": "UserIsBlocked"
                }

            except PeerIdInvalid:
                # Некорректный telegram_id → пропустить без retry
                logger.warning(
                    f"❌ Некорректный telegram_id: {username} (ID: {telegram_id})"
                )
                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "status": "failed",
                    "error": "PeerIdInvalid"
                }

            except FloodWait as e:
                # Telegram API rate limit → ждать указанное время
                wait_time = e.value
                logger.warning(
                    f"⏳ FloodWait для {username} (ID: {telegram_id}): "
                    f"ожидание {wait_time} секунд"
                )
                await asyncio.sleep(wait_time)
                # Продолжить попытки после ожидания
                continue

            except RPCError as e:
                # Другие ошибки Telegram API
                if attempt < max_retries:
                    # Exponential backoff: 1s → 2s → 4s
                    backoff_delay = 2 ** attempt
                    logger.warning(
                        f"⚠️ Ошибка отправки {username} (ID: {telegram_id}): {e}. "
                        f"Retry через {backoff_delay}s (попытка {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    # Максимум попыток исчерпан
                    logger.error(
                        f"❌ Не удалось отправить пароль {username} (ID: {telegram_id}) "
                        f"после {max_retries + 1} попыток: {e}"
                    )
                    return {
                        "telegram_id": telegram_id,
                        "username": username,
                        "status": "failed",
                        "error": str(e)
                    }

            except Exception as e:
                # Непредвиденные ошибки
                logger.error(
                    f"❌ Неожиданная ошибка при отправке {username} (ID: {telegram_id}): {e}",
                    exc_info=True
                )
                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "status": "failed",
                    "error": f"Unexpected error: {str(e)}"
                }

        # Fallback (не должно достигаться при нормальном выполнении)
        return {
            "telegram_id": telegram_id,
            "username": username,
            "status": "failed",
            "error": "Max retries exceeded"
        }

    async def send_passwords_to_users(self, migrated_users: List[Dict]) -> Dict:
        """
        Отправляет пароли всем мигрированным пользователям.

        Логика:
        1. Для каждого пользователя: отправить пароль + обработать результат
        2. Rate limiting: 1 секунда задержки между отправками
        3. Собрать статистику успешных и неудачных отправок

        Args:
            migrated_users: Список мигрированных пользователей из migration_report.json
                Формат: [{"telegram_id": int, "username": str, "temp_password": str, ...}, ...]

        Returns:
            dict: Отчет о доставке с полями:
                - delivery_date: str (ISO timestamp)
                - total_users: int
                - sent: list (успешно отправленные)
                - failed: list (ошибки отправки)
        """
        logger.info(f"Начало отправки паролей {len(migrated_users)} пользователям")

        for i, user in enumerate(migrated_users, start=1):
            telegram_id = user["telegram_id"]
            username = user["username"]
            temp_password = user["temp_password"]

            logger.info(
                f"[{i}/{len(migrated_users)}] Отправка пароля: {username} (ID: {telegram_id})"
            )

            # Отправить пароль с retry
            result = await self._send_password_with_retry(
                telegram_id=telegram_id,
                username=username,
                temp_password=temp_password
            )

            # Сохранить результат
            if result["status"] == "success":
                self.sent_users.append(result)
            else:
                self.failed_users.append(result)

            # Rate limiting: 1 секунда задержки между отправками
            # (пропустить задержку для последнего пользователя)
            if i < len(migrated_users):
                await asyncio.sleep(1)

        # Сформировать отчет о доставке
        report = {
            "delivery_date": datetime.now().isoformat(),
            "total_users": len(migrated_users),
            "sent": self.sent_users,
            "failed": self.failed_users
        }

        logger.info(
            f"Отправка завершена: {len(self.sent_users)} успешно, "
            f"{len(self.failed_users)} ошибок"
        )

        return report

    def save_delivery_report(self, report: Dict, output_path: Path) -> None:
        """
        Сохраняет отчет о доставке паролей в JSON файл.

        Args:
            report: Отчет о доставке (результат send_passwords_to_users)
            output_path: Путь к файлу для сохранения
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Отчет о доставке сохранен: {output_path}")

        except Exception as e:
            logger.error(f"Не удалось сохранить отчет о доставке: {e}", exc_info=True)


def load_migration_report(report_path: Path) -> Dict:
    """
    Загружает migration_report.json с результатами миграции.

    Args:
        report_path: Путь к migration_report.json

    Returns:
        dict: Содержимое migration_report.json

    Raises:
        FileNotFoundError: Если файл не найден
        ValueError: Если файл имеет некорректный формат
    """
    if not report_path.exists():
        raise FileNotFoundError(
            f"Migration report не найден: {report_path}\n"
            f"Сначала запустите scripts/migrate_users.py для создания отчета."
        )

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        # Валидация структуры
        if "migrated" not in report:
            raise ValueError(
                f"Migration report имеет некорректный формат: отсутствует поле 'migrated'"
            )

        logger.info(
            f"Migration report загружен: {len(report['migrated'])} пользователей для отправки"
        )

        return report

    except json.JSONDecodeError as e:
        raise ValueError(f"Migration report содержит некорректный JSON: {e}")


async def main():
    """
    Главная функция скрипта отправки паролей.

    Выполняет:
    1. Загрузку migration_report.json
    2. Инициализацию Pyrogram Client (bot)
    3. Отправку паролей всем мигрированным пользователям
    4. Сохранение отчета о доставке
    5. Предложение удалить migration_report.json
    """
    logger.info("=== VoxPersona Password Delivery Script ===")

    # Определить пути
    base_dir = Path(__file__).parent.parent
    auth_data_path = base_dir / "src" / "auth_data"
    migration_report_path = auth_data_path / "migration_report.json"
    delivery_report_path = auth_data_path / "password_delivery_report.json"

    # 1. Загрузить migration_report.json
    try:
        migration_report = load_migration_report(migration_report_path)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Ошибка загрузки migration report: {e}")
        return

    migrated_users = migration_report["migrated"]

    if not migrated_users:
        logger.warning("Нет пользователей для отправки паролей (migrated list пуст)")
        return

    logger.info(f"Пользователей для отправки паролей: {len(migrated_users)}")

    # 2. Инициализировать Pyrogram Client (bot)
    client = Client(
        name=f"{SESSION_NAME}_bot",  # Отдельная сессия для бота
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=TELEGRAM_BOT_TOKEN,  # Использовать bot_token вместо user session
        workdir=str(base_dir / "src")
    )

    async with client:
        logger.info("Telegram Bot Client подключен")

        # 3. Создать сервис доставки паролей
        delivery_service = PasswordDeliveryService(pyrogram_client=client)

        # 4. Отправить пароли всем пользователям
        delivery_report = await delivery_service.send_passwords_to_users(migrated_users)

        # 5. Сохранить отчет о доставке
        delivery_service.save_delivery_report(delivery_report, delivery_report_path)

        # 6. Вывести итоговую статистику
        logger.info("=== Delivery Summary ===")
        logger.info(f"Всего пользователей: {delivery_report['total_users']}")
        logger.info(f"Успешно отправлено: {len(delivery_report['sent'])}")
        logger.info(f"Ошибок: {len(delivery_report['failed'])}")

        if delivery_report['sent']:
            logger.info("\n--- Успешно отправлено ---")
            for user in delivery_report['sent']:
                logger.info(f"  ✅ {user['username']} (ID: {user['telegram_id']})")

        if delivery_report['failed']:
            logger.warning("\n--- Ошибки отправки ---")
            for user in delivery_report['failed']:
                logger.warning(
                    f"  ❌ {user['username']} (ID: {user['telegram_id']}) - "
                    f"Ошибка: {user['error']}"
                )

        logger.info(f"\nОтчет о доставке сохранен: {delivery_report_path}")

        # 7. Предложение удалить migration_report.json
        if delivery_report['failed']:
            logger.warning(
                f"\n⚠️ ВНИМАНИЕ: Есть ошибки доставки ({len(delivery_report['failed'])} пользователей)."
            )
            logger.warning(
                f"НЕ УДАЛЯЙТЕ migration_report.json до повторной отправки неудачным пользователям."
            )
        else:
            logger.info(
                f"\n✅ Все пароли успешно отправлены!"
            )
            logger.info(
                f"⚠️ РЕКОМЕНДАЦИЯ: Удалите migration_report.json для безопасности:"
            )
            logger.info(f"   rm {migration_report_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Отправка прервана пользователем")
    except Exception as e:
        logger.error(f"Отправка паролей завершилась с ошибкой: {e}", exc_info=True)
        sys.exit(1)
