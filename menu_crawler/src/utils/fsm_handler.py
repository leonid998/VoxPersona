"""
FSM Handler для Menu Crawler
Обработка многошаговых сценариев (FSM) в боте
"""

import asyncio
import structlog
from typing import Optional, Dict, Any


logger = structlog.get_logger(__name__)


class FSMHandler:
    """
    Обработчик FSM (Finite State Machine) сценариев.

    Позволяет crawler проходить многошаговые диалоги:
    - new_chat → выбор режима → ввод данных
    - rename_chat → ввод нового названия
    - report_delete → подтверждение удаления
    """

    # Словарь FSM шаблонов для автоматических ответов
    FSM_PATTERNS = {
        # new_chat FSM
        "new_chat": {
            "expected_messages": [
                "Введите название чата",
                "Выберите режим"
            ],
            "responses": [
                "Тестовый чат Menu Crawler",  # Название чата
                "skip"  # Пропускаем выбор режима (используем callback)
            ]
        },

        # rename_chat FSM
        "rename_chat": {
            "expected_messages": [
                "Введите новое название"
            ],
            "responses": [
                "Переименованный чат"
            ]
        },

        # change_password FSM (если TEST_USER захочет сменить пароль)
        "change_password": {
            "expected_messages": [
                "Введите текущий пароль",
                "Введите новый пароль",
                "Подтвердите новый пароль"
            ],
            "responses": [
                "cancel",  # Отменяем смену пароля
                "cancel",
                "cancel"
            ]
        },

        # edit_data FSM
        "edit_data": {
            "expected_messages": [
                "Введите значение"
            ],
            "responses": [
                "Тестовое значение"
            ]
        }
    }

    def __init__(self, client, bot_username: str, throttle_delay: float = 2.0):
        """
        Инициализация FSM Handler.

        Args:
            client: Pyrogram Client
            bot_username: Username бота (например, @market_res_bot)
            throttle_delay: Задержка между сообщениями (сек)
        """
        self.client = client
        self.bot_username = bot_username
        self.throttle_delay = throttle_delay

        self.current_fsm: Optional[str] = None  # Текущий FSM сценарий
        self.fsm_step: int = 0  # Текущий шаг в FSM

        logger.info(
            "fsm_handler_initialized",
            throttle_delay=throttle_delay
        )

    def start_fsm(self, callback_data: str):
        """
        Запуск FSM сценария.

        Args:
            callback_data: callback_data, который активирует FSM
        """
        # Определение FSM сценария по callback_data
        if callback_data == "new_chat":
            self.current_fsm = "new_chat"
        elif callback_data.startswith("rename_chat"):
            self.current_fsm = "rename_chat"
        elif callback_data.startswith("change_password"):
            self.current_fsm = "change_password"
        elif callback_data.startswith("edit_"):
            self.current_fsm = "edit_data"
        else:
            self.current_fsm = None

        if self.current_fsm:
            self.fsm_step = 0
            logger.info(
                "fsm_started",
                fsm=self.current_fsm,
                callback_data=callback_data
            )

    async def handle_fsm_message(self, message_text: str) -> Optional[str]:
        """
        Обработка сообщения от бота в FSM режиме.

        Возвращает текст ответа или 'skip' для пропуска.

        Args:
            message_text: Текст сообщения от бота

        Returns:
            Текст ответа или None если FSM не активен
        """
        if not self.current_fsm:
            return None

        pattern = self.FSM_PATTERNS.get(self.current_fsm)
        if not pattern:
            logger.warning(
                "fsm_pattern_not_found",
                fsm=self.current_fsm
            )
            return None

        # Проверка ожидаемого сообщения
        expected_messages = pattern["expected_messages"]
        responses = pattern["responses"]

        if self.fsm_step >= len(expected_messages):
            # FSM завершен
            logger.info(
                "fsm_completed",
                fsm=self.current_fsm,
                steps=self.fsm_step
            )
            self.current_fsm = None
            self.fsm_step = 0
            return None

        # Получение ответа для текущего шага
        response = responses[self.fsm_step]

        logger.info(
            "fsm_step_processed",
            fsm=self.current_fsm,
            step=self.fsm_step,
            expected=expected_messages[self.fsm_step],
            response=response
        )

        self.fsm_step += 1

        # Если ответ = "skip", пропускаем отправку текста
        if response == "skip":
            return None

        # Если ответ = "cancel", отправляем /cancel
        if response == "cancel":
            return "/cancel"

        return response

    async def send_text_response(self, response: str):
        """
        Отправка текстового ответа боту.

        Args:
            response: Текст ответа
        """
        await asyncio.sleep(self.throttle_delay)

        await self.client.send_message(self.bot_username, response)

        logger.info(
            "fsm_text_sent",
            response=response
        )

    def is_active(self) -> bool:
        """Проверка, активен ли FSM сценарий"""
        return self.current_fsm is not None

    def reset(self):
        """Сброс FSM состояния"""
        self.current_fsm = None
        self.fsm_step = 0
        logger.info("fsm_reset")
