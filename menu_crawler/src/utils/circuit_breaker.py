"""
Circuit Breaker для обработки Telegram Rate Limits.

Реализует exponential backoff для FloodWait ошибок от Telegram API.
Предотвращает перегрузку API и обеспечивает graceful degradation.
"""

import asyncio
import structlog
from pyrogram.errors import FloodWait

# Получить structured logger
logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker паттерн для обработки Rate Limit ошибок.

    Использует exponential backoff стратегию:
    - 1-я попытка: ждём 2^1 = 2 секунды
    - 2-я попытка: ждём 2^2 = 4 секунды
    - 3-я попытка: ждём 2^3 = 8 секунд
    - После 3-х неудач: открываем circuit (прекращаем попытки)

    Attributes:
        max_failures (int): Максимальное количество неудач перед открытием circuit
        backoff_base (float): База для exponential backoff (по умолчанию 2.0)
        failures (int): Текущее количество последовательных неудач
    """

    def __init__(self, max_failures: int = 3, backoff_base: float = 2.0):
        """
        Инициализация Circuit Breaker.

        Args:
            max_failures: Максимум неудач перед открытием circuit (default: 3)
            backoff_base: База для exponential backoff (default: 2.0)
        """
        self.max_failures = max_failures
        self.backoff_base = backoff_base
        self.failures = 0

        logger.info(
            "circuit_breaker_initialized",
            max_failures=max_failures,
            backoff_base=backoff_base
        )

    def reset(self) -> None:
        """
        Сбросить счётчик неудач после успешного запроса.

        Вызывается когда запрос прошёл успешно, чтобы начать отсчёт с нуля.
        """
        if self.failures > 0:
            logger.info("circuit_breaker_reset", previous_failures=self.failures)
            self.failures = 0

    async def handle_error(self, error: FloodWait) -> bool:
        """
        Обработать FloodWait ошибку от Telegram API.

        Стратегия:
        1. Инкрементировать счётчик неудач
        2. Если достигнут max_failures → открыть circuit (вернуть False)
        3. Рассчитать exponential backoff delay
        4. Использовать max(exponential_delay, recommended_delay от Telegram)
        5. Подождать нужное время
        6. Вернуть True (разрешить retry)

        Args:
            error: FloodWait ошибка из Pyrogram
                   error.value содержит рекомендуемое время ожидания в секундах

        Returns:
            True - если следует повторить попытку (retry)
            False - если circuit открыт (следует прекратить попытки)

        Example:
            >>> breaker = CircuitBreaker(max_failures=3)
            >>> try:
            ...     await client.send_callback_query(...)
            ... except FloodWait as e:
            ...     if await breaker.handle_error(e):
            ...         # Retry запрос
            ...         await client.send_callback_query(...)
            ...     else:
            ...         # Circuit opened - прекращаем попытки
            ...         break
        """
        self.failures += 1

        # Проверка: достигнут ли лимит неудач?
        if self.failures >= self.max_failures:
            logger.error(
                "circuit_breaker_opened",
                failures=self.failures,
                max_failures=self.max_failures,
                message="Достигнут лимит неудач. Circuit открыт, прекращаем попытки."
            )
            return False

        # Рассчитать exponential backoff delay
        exponential_delay = self.backoff_base ** self.failures

        # FloodWait.value содержит рекомендуемое время от Telegram
        recommended_delay = error.value if hasattr(error, 'value') else exponential_delay

        # Выбрать максимальное из двух (для безопасности)
        wait_time = max(exponential_delay, recommended_delay)

        logger.warning(
            "rate_limit_hit",
            attempt=self.failures,
            max_failures=self.max_failures,
            exponential_delay=exponential_delay,
            recommended_delay=recommended_delay,
            wait_seconds=wait_time,
            message=f"Rate limit достигнут. Ожидание {wait_time:.1f} сек перед повтором..."
        )

        # Подождать перед retry
        await asyncio.sleep(wait_time)

        logger.info(
            "rate_limit_retry",
            attempt=self.failures,
            message=f"Повтор попытки после ожидания {wait_time:.1f} сек"
        )

        return True

    def is_open(self) -> bool:
        """
        Проверить, открыт ли circuit.

        Returns:
            True если circuit открыт (достигнут max_failures)
            False если circuit закрыт (можно продолжать попытки)
        """
        return self.failures >= self.max_failures

    def get_state(self) -> dict:
        """
        Получить текущее состояние Circuit Breaker.

        Returns:
            Словарь с состоянием:
            - failures: текущее количество неудач
            - max_failures: лимит неудач
            - is_open: открыт ли circuit
            - next_delay: следующий delay при ошибке

        Example:
            >>> state = breaker.get_state()
            >>> print(f"Circuit state: {state}")
            {'failures': 2, 'max_failures': 3, 'is_open': False, 'next_delay': 4.0}
        """
        next_delay = self.backoff_base ** (self.failures + 1) if not self.is_open() else None

        return {
            "failures": self.failures,
            "max_failures": self.max_failures,
            "is_open": self.is_open(),
            "next_delay": next_delay
        }


# Пример использования
async def example_usage():
    """Демонстрация использования CircuitBreaker."""
    from pyrogram import Client

    # Инициализация
    breaker = CircuitBreaker(max_failures=3, backoff_base=2.0)

    # Симуляция запросов с Rate Limit
    for i in range(5):
        try:
            # Симуляция FloodWait ошибки
            raise FloodWait(value=1)  # Telegram рекомендует ждать 1 сек

        except FloodWait as e:
            print(f"\n[Попытка {i+1}] FloodWait ошибка!")

            # Обработка через Circuit Breaker
            should_retry = await breaker.handle_error(e)

            if should_retry:
                print(f"✅ Retry разрешён. Состояние: {breaker.get_state()}")
                # Здесь был бы retry запроса
            else:
                print(f"❌ Circuit открыт. Прекращаем попытки.")
                print(f"Финальное состояние: {breaker.get_state()}")
                break

        else:
            # Успех - сброс счётчика
            breaker.reset()
            print(f"✅ Запрос успешен. Circuit сброшен.")


if __name__ == "__main__":
    # Запуск примера
    asyncio.run(example_usage())
