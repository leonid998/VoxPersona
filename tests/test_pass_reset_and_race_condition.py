"""
Тесты для проверки исправлений из task 06_pass_block.

Проверяет решение 2 проблем из task.txt:
1. Сброс пароля anna35 (ImportError iso_to_datetime)
2. Разблокировка Elena admin (race condition asyncio.to_thread)

Автор: VoxPersona Team
Дата: 07 ноября 2025
"""

import re
import inspect
from pathlib import Path


class TestPassResetAndRaceCondition:
    """Тесты исправлений сброса пароля и race condition"""

    def setup_method(self):
        """Подготовка к тестам"""
        self.auth_storage_path = Path("src/auth_storage.py")
        self.access_handlers_path = Path("src/access_handlers.py")
        self.auth_models_path = Path("src/auth_models.py")

        # Прочитать содержимое файлов
        with open(self.auth_storage_path, "r", encoding="utf-8") as f:
            self.auth_storage_content = f.read()

        with open(self.access_handlers_path, "r", encoding="utf-8") as f:
            self.access_handlers_content = f.read()

        with open(self.auth_models_path, "r", encoding="utf-8") as f:
            self.auth_models_content = f.read()

    # ========== ГРУППА A: Тесты импорта iso_to_datetime ==========

    def test_iso_to_datetime_exists_in_auth_models(self):
        """
        Проверка что функция iso_to_datetime определена в auth_models.py
        """
        # Проверить что функция существует
        pattern = r'def iso_to_datetime\('
        assert re.search(pattern, self.auth_models_content), \
            "ОШИБКА: Функция iso_to_datetime не найдена в auth_models.py!"

    def test_iso_to_datetime_correct_import_in_auth_storage(self):
        """
        Проблема #1: Правильный импорт iso_to_datetime.

        Проверяет что в auth_storage.py:318
        используется правильный импорт:
        from auth_models import iso_to_datetime
        """
        # Найти функцию update_user_password
        pattern = r'def update_user_password\(.*?\):.*?(?=\n    def |\Z)'
        match = re.search(pattern, self.auth_storage_content, re.DOTALL)

        assert match, "Функция update_user_password не найдена в auth_storage.py"

        function_body = match.group(0)

        # Проверить что есть правильный импорт
        correct_import = "from auth_models import iso_to_datetime"
        assert correct_import in function_body, \
            f"ОШИБКА: Не найден правильный импорт '{correct_import}' в update_user_password()!"

    def test_no_wrong_import_from_utils(self):
        """
        Проверка что НЕТ неправильного импорта из utils.

        Проверяет что в update_user_password()
        НЕТ строки: from utils import iso_to_datetime
        """
        # Найти функцию update_user_password
        pattern = r'def update_user_password\(.*?\):.*?(?=\n    def |\Z)'
        match = re.search(pattern, self.auth_storage_content, re.DOTALL)

        assert match, "Функция update_user_password не найдена"

        function_body = match.group(0)

        # Проверить что НЕТ неправильного импорта
        wrong_import = "from utils import iso_to_datetime"
        assert wrong_import not in function_body, \
            f"ОШИБКА: Найден неправильный импорт '{wrong_import}' в update_user_password()!"

    # ========== ГРУППА B: Тесты race condition ==========

    def test_no_asyncio_to_thread_in_handle_user_details(self):
        """
        Проблема #2: Убран asyncio.to_thread.

        Проверяет что в функции handle_user_details
        НЕТ строки: await asyncio.to_thread(auth.storage.get_user, user_id)
        """
        # Найти функцию handle_user_details
        pattern = r'async def handle_user_details\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_user_details не найдена в access_handlers.py"

        function_body = match.group(0)

        # Проверить что НЕТ asyncio.to_thread для get_user
        assert "asyncio.to_thread" not in function_body, \
            "ОШИБКА: Найден asyncio.to_thread в handle_user_details() - race condition не устранена!"

    def test_synchronous_get_user_call_in_handle_user_details(self):
        """
        Проверка что get_user вызывается синхронно.

        Проверяет что в handle_user_details есть прямой вызов:
        user = auth.storage.get_user(user_id)
        (без await, без asyncio.to_thread)
        """
        # Найти функцию handle_user_details
        pattern = r'async def handle_user_details\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_user_details не найдена"

        function_body = match.group(0)

        # Проверить что есть синхронный вызов get_user
        # Паттерн: user = auth.storage.get_user(...)
        sync_call_pattern = r'user\s*=\s*auth\.storage\.get_user\('
        assert re.search(sync_call_pattern, function_body), \
            "ОШИБКА: Не найден синхронный вызов auth.storage.get_user() в handle_user_details()!"

    def test_no_await_before_get_user_in_handle_user_details(self):
        """
        Проверка что перед get_user НЕТ await.

        Убеждается что вызов get_user действительно синхронный,
        а не асинхронный (нет await перед вызовом).
        """
        # Найти функцию handle_user_details
        pattern = r'async def handle_user_details\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_user_details не найдена"

        function_body = match.group(0)

        # Проверить что НЕТ await перед get_user
        await_pattern = r'await\s+auth\.storage\.get_user\('
        assert not re.search(await_pattern, function_body), \
            "ОШИБКА: Найден await перед auth.storage.get_user() - вызов должен быть синхронным!"

    def test_no_asyncio_to_thread_anywhere_in_access_handlers(self):
        """
        Проверка что asyncio.to_thread полностью удален из access_handlers.py.

        Убеждается что НЕТ других использований asyncio.to_thread
        которые могли бы вызвать race condition.
        """
        # Проверить весь файл access_handlers.py
        pattern = r'asyncio\.to_thread\('
        matches = list(re.finditer(pattern, self.access_handlers_content))

        assert len(matches) == 0, \
            f"ОШИБКА: Найдено {len(matches)} использований asyncio.to_thread в access_handlers.py!"

    # ========== ГРУППА C: Интеграционные тесты ==========

    def test_get_user_uses_threading_lock(self):
        """
        Проверка что get_user использует threading.Lock.

        Убеждается что функция get_user в auth_storage.py
        использует lock для thread-safe операций.
        """
        # Найти функцию get_user
        pattern = r'def get_user\(self.*?\):.*?(?=\n    def |\Z)'
        match = re.search(pattern, self.auth_storage_content, re.DOTALL)

        assert match, "Функция get_user не найдена в auth_storage.py"

        function_body = match.group(0)

        # Проверить что используется lock
        assert "with lock:" in function_body or "lock.acquire()" in function_body, \
            "ОШИБКА: Функция get_user не использует threading.Lock для синхронизации!"

    def test_update_user_uses_threading_lock(self):
        """
        Проверка что update_user использует threading.Lock.

        Убеждается что функция update_user в auth_storage.py
        использует lock для thread-safe операций.
        """
        # Найти функцию update_user
        pattern = r'def update_user\(self.*?\):.*?(?=\n    def |\Z)'
        match = re.search(pattern, self.auth_storage_content, re.DOTALL)

        assert match, "Функция update_user не найдена в auth_storage.py"

        function_body = match.group(0)

        # Проверить что используется lock
        assert "with lock:" in function_body or "lock.acquire()" in function_body, \
            "ОШИБКА: Функция update_user не использует threading.Lock для синхронизации!"

    # ========== Итоговый тест ==========

    def test_all_fixes_applied(self):
        """
        Итоговый тест: все 2 проблемы решены.

        Суммарная проверка всех исправлений из task.txt.
        """
        issues_solved = []

        # Проблема 1: Правильный импорт iso_to_datetime
        if "from auth_models import iso_to_datetime" in self.auth_storage_content:
            # Убедиться что нет неправильного импорта
            update_password_func = re.search(
                r'def update_user_password\(.*?\):.*?(?=\n    def |\Z)',
                self.auth_storage_content,
                re.DOTALL
            )
            if update_password_func and "from utils import iso_to_datetime" not in update_password_func.group(0):
                issues_solved.append(1)

        # Проблема 2: Убран asyncio.to_thread
        handle_user_details_func = re.search(
            r'async def handle_user_details\(.*?\):.*?(?=\nasync def|\Z)',
            self.access_handlers_content,
            re.DOTALL
        )
        if handle_user_details_func:
            func_body = handle_user_details_func.group(0)
            # Проверить что НЕТ asyncio.to_thread
            if "asyncio.to_thread" not in func_body:
                # И есть синхронный вызов get_user
                if re.search(r'user\s*=\s*auth\.storage\.get_user\(', func_body):
                    issues_solved.append(2)

        # Обе проблемы должны быть решены
        assert len(issues_solved) == 2, \
            f"Решено только {len(issues_solved)} из 2 проблем: {issues_solved}"

        print(f"\n✅ ОБЕ ПРОБЛЕМЫ УСПЕШНО РЕШЕНЫ: {issues_solved}")
        print("  1. Импорт iso_to_datetime исправлен (auth_storage.py:318)")
        print("  2. Race condition устранена (access_handlers.py:284)")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
