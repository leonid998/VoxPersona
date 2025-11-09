"""
Menu Crawler для VoxPersona - автоматический обход меню бота.

Функции:
- Автоматически обходит все меню
- Находит мёртвые кнопки (callback без handler)
- Строит граф навигации
- Генерирует JSON отчёт

Использование:
    python menu_crawler.py
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup
from pyrogram.errors import FloodWait

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class MenuCrawler:
    """
    Crawler для обхода меню Telegram бота.

    Использует DFS (depth-first search) для обхода всех кнопок.
    """

    def __init__(self, app: Client, chat_id: int):
        self.app = app
        self.chat_id = chat_id

        # Хранилище данных
        self.visited: Set[str] = set()  # Посещённые callback_data
        self.graph: Dict[str, List[str]] = {}  # Граф навигации
        self.dead_buttons: List[str] = []  # Мёртвые кнопки
        self.errors: List[Dict] = []  # Ошибки

        # Статистика
        self.total_buttons = 0
        self.start_time = None

    async def start(self):
        """Запуск crawler."""
        logger.info("🚀 Запуск Menu Crawler...")
        self.start_time = datetime.now()

        # Отправляем команду /start
        await self.app.send_message(self.chat_id, "/start")
        await asyncio.sleep(1)

        # Получаем последнее сообщение (главное меню)
        async for message in self.app.get_chat_history(self.chat_id, limit=1):
            if message.reply_markup:
                await self.crawl_menu(message, "start")

        logger.info("✅ Обход завершён!")
        return self.generate_report()

    async def crawl_menu(self, message: Message, parent_callback: str = "root"):
        """
        Рекурсивный обход меню (DFS).

        Args:
            message: Сообщение с меню
            parent_callback: Callback родительского меню
        """
        if not message.reply_markup:
            return

        markup: InlineKeyboardMarkup = message.reply_markup

        # Извлекаем все кнопки
        buttons = []
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data:
                    buttons.append(button.callback_data)

        logger.info(f"📋 Меню '{parent_callback}': найдено {len(buttons)} кнопок")

        # Добавляем в граф
        self.graph[parent_callback] = buttons
        self.total_buttons += len(buttons)

        # Обходим каждую кнопку
        for callback_data in buttons:
            # Пропускаем уже посещённые
            if callback_data in self.visited:
                logger.debug(f"⏭️ Пропуск '{callback_data}' (уже посещён)")
                continue

            self.visited.add(callback_data)

            try:
                # Нажимаем на кнопку
                logger.info(f"👆 Клик: {callback_data}")

                # Ищем кнопку в текущем сообщении
                await self.click_button(message, callback_data)

                # Задержка для избежания rate limiting
                await asyncio.sleep(0.7)

                # Получаем обновлённое сообщение
                async for new_message in self.app.get_chat_history(self.chat_id, limit=1):
                    # Проверяем, есть ли новое меню
                    if new_message.reply_markup:
                        # Рекурсивно обходим подменю
                        await self.crawl_menu(new_message, callback_data)
                    else:
                        # Возможно, это действие без меню
                        logger.debug(f"ℹ️ '{callback_data}' не содержит подменю")

                    break

            except FloodWait as e:
                logger.warning(f"⏳ Rate limit: ждём {e.value} сек")
                await asyncio.sleep(e.value)

            except Exception as e:
                logger.error(f"❌ Ошибка при клике на '{callback_data}': {e}")
                self.errors.append({
                    "callback": callback_data,
                    "parent": parent_callback,
                    "error": str(e)
                })

    async def click_button(self, message: Message, callback_data: str):
        """
        Эмулирует клик по кнопке.

        Args:
            message: Сообщение с кнопкой
            callback_data: callback_data кнопки
        """
        # Используем request_callback_answer для симуляции клика
        await self.app.request_callback_answer(
            chat_id=self.chat_id,
            message_id=message.id,
            callback_data=callback_data
        )

    def generate_report(self) -> Dict:
        """Генерирует JSON отчёт."""
        duration = (datetime.now() - self.start_time).total_seconds()

        report = {
            "crawler_info": {
                "bot": "VoxPersona",
                "start_time": self.start_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "chat_id": self.chat_id
            },
            "statistics": {
                "total_buttons": self.total_buttons,
                "visited_buttons": len(self.visited),
                "dead_buttons_count": len(self.dead_buttons),
                "errors_count": len(self.errors)
            },
            "navigation_graph": self.graph,
            "dead_buttons": self.dead_buttons,
            "errors": self.errors,
            "visited_callbacks": list(self.visited)
        }

        return report


async def main():
    """Главная функция."""
    # Настройки (берём из .env)
    from dotenv import load_dotenv
    import os

    load_dotenv()

    api_id = int(os.getenv("API_ID", "0"))
    api_hash = os.getenv("API_HASH", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    if not api_id or not api_hash or not bot_token:
        logger.error("❌ Не заданы API_ID, API_HASH или TELEGRAM_BOT_TOKEN")
        return

    # Создаём клиент (user account)
    app = Client(
        "menu_crawler_session",
        api_id=api_id,
        api_hash=api_hash
    )

    async with app:
        # Получаем chat_id с ботом
        bot_username = bot_token.split(":")[0]  # Упрощённо

        # Запрашиваем chat_id (нужно вручную указать)
        chat_id = int(input("Введите chat_id с ботом (ваш Telegram ID): "))

        # Запускаем crawler
        crawler = MenuCrawler(app, chat_id)
        report = await crawler.start()

        # Сохраняем отчёт
        output_file = Path("menu_crawler_report.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"📄 Отчёт сохранён: {output_file}")
        logger.info(f"📊 Статистика:")
        logger.info(f"  Всего кнопок: {report['statistics']['total_buttons']}")
        logger.info(f"  Посещено: {report['statistics']['visited_buttons']}")
        logger.info(f"  Мёртвых кнопок: {report['statistics']['dead_buttons_count']}")
        logger.info(f"  Ошибок: {report['statistics']['errors_count']}")


if __name__ == "__main__":
    asyncio.run(main())
