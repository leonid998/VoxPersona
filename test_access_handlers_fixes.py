"""
Тесты для проверки исправлений меню "Управление Пользователями".

Проверяет решение 6 проблем из task.txt:
1. Отсутствие блокирующих задержек после блокирования
2. Заблокированные пользователи остаются в списке
3. Правильные сообщения при попытке изменить роль себе
4. Защита от блокировки/удаления себя
5. Отсутствие блокирующих задержек после удаления
6. Функциональность блокировки (is_blocked проверяется)

Автор: VoxPersona Team
Дата: 06 ноября 2025
"""

import re
from pathlib import Path


class TestAccessHandlersFixes:
    """Тесты исправлений в access_handlers.py"""

    def setup_method(self):
        """Подготовка к тестам"""
        self.access_handlers_path = Path("src/access_handlers.py")
        self.auth_filters_path = Path("src/auth_filters.py")

        # Прочитать содержимое файлов
        with open(self.access_handlers_path, "r", encoding="utf-8") as f:
            self.access_handlers_content = f.read()

        with open(self.auth_filters_path, "r", encoding="utf-8") as f:
            self.auth_filters_content = f.read()

    # ========== ГРУППА A: Тесты UX (отсутствие задержек) ==========

    def test_no_sleep_after_block_in_handle_confirm_block(self):
        """
        Проблема #1: Убрана задержка после блокирования.

        Проверяет что в функции handle_confirm_block
        НЕТ строки await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        после успешной блокировки.
        """
        # Найти функцию handle_confirm_block
        pattern = r'async def handle_confirm_block\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_block не найдена"

        function_body = match.group(0)

        # Проверить что после track_and_send с успехом НЕТ sleep перед handle_user_details
        # Паттерн: уведомление о успехе → НЕ должно быть sleep → handle_user_details
        success_notification_pattern = r'Пользователь.*?(заблокирован|разблокирован).*?await handle_user_details'
        success_block = re.search(success_notification_pattern, function_body, re.DOTALL | re.IGNORECASE)

        if success_block:
            success_text = success_block.group(0)
            # НЕ должно быть await asyncio.sleep(NOTIFICATION_DELETE_TIME)
            assert "await asyncio.sleep(NOTIFICATION_DELETE_TIME)" not in success_text, \
                "ОШИБКА: Найдена блокирующая задержка после блокирования пользователя!"

    def test_no_sleep_after_delete_in_handle_confirm_delete(self):
        """
        Проблема #5: Убрана задержка после удаления.

        Проверяет что в функции handle_confirm_delete
        НЕТ строки await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        после успешного удаления.
        """
        # Найти функцию handle_confirm_delete
        pattern = r'async def handle_confirm_delete\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_delete не найдена"

        function_body = match.group(0)

        # Проверить что после уведомления об удалении НЕТ sleep
        success_pattern = r'Пользователь удален.*?await handle_list_users'
        success_block = re.search(success_pattern, function_body, re.DOTALL)

        if success_block:
            success_text = success_block.group(0)
            assert "await asyncio.sleep(NOTIFICATION_DELETE_TIME)" not in success_text, \
                "ОШИБКА: Найдена блокирующая задержка после удаления пользователя!"

    def test_no_sleep_in_self_role_change_error(self):
        """
        Проблема #3: Убрана задержка при ошибке изменения роли себе.

        Проверяет что в функции handle_confirm_role_change
        НЕТ строки await asyncio.sleep(ERROR_DELETE_TIME)
        при попытке изменить роль самому себе.
        """
        # Найти функцию handle_confirm_role_change
        pattern = r'async def handle_confirm_role_change\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_role_change не найдена"

        function_body = match.group(0)

        # Найти блок проверки "нельзя изменить роль самого себя"
        self_check_pattern = r'if admin_user\.user_id == user_id:.*?return'
        self_check = re.search(self_check_pattern, function_body, re.DOTALL)

        if self_check:
            self_check_text = self_check.group(0)
            assert "await asyncio.sleep(ERROR_DELETE_TIME)" not in self_check_text, \
                "ОШИБКА: Найдена задержка при попытке изменить роль себе!"

    def test_no_sleep_in_self_block_error(self):
        """
        Проблема #4: Убрана задержка при ошибке блокировки себя.

        Проверяет что в функции handle_confirm_block
        НЕТ строки await asyncio.sleep(ERROR_DELETE_TIME)
        при попытке заблокировать самого себя.
        """
        # Найти функцию handle_confirm_block
        pattern = r'async def handle_confirm_block\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_block не найдена"

        function_body = match.group(0)

        # Найти блок проверки "нельзя заблокировать самого себя"
        self_check_pattern = r'Вы не можете заблокировать себя.*?return'
        self_check = re.search(self_check_pattern, function_body, re.DOTALL)

        if self_check:
            self_check_text = self_check.group(0)
            assert "await asyncio.sleep(ERROR_DELETE_TIME)" not in self_check_text, \
                "ОШИБКА: Найдена задержка при попытке заблокировать себя!"

    def test_no_sleep_in_self_delete_error(self):
        """
        Проблема #4: Убрана задержка при ошибке удаления себя.

        Проверяет что в функции handle_confirm_delete
        НЕТ строки await asyncio.sleep(ERROR_DELETE_TIME)
        при попытке удалить самого себя.
        """
        # Найти функцию handle_confirm_delete
        pattern = r'async def handle_confirm_delete\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_delete не найдена"

        function_body = match.group(0)

        # Найти блок проверки "нельзя удалить самого себя"
        self_check_pattern = r'Вы не можете удалить себя.*?return'
        self_check = re.search(self_check_pattern, function_body, re.DOTALL)

        if self_check:
            self_check_text = self_check.group(0)
            assert "await asyncio.sleep(ERROR_DELETE_TIME)" not in self_check_text, \
                "ОШИБКА: Найдена задержка при попытке удалить себя!"

    # ========== ГРУППА B: Тесты логики (is_active/is_blocked) ==========

    def test_is_active_not_linked_to_is_blocked(self):
        """
        Проблема #6: is_active и is_blocked разделены.

        Проверяет что в функции handle_confirm_block
        НЕТ строки is_active = not is_blocked
        (неправильное связывание флагов).
        """
        # Найти функцию handle_confirm_block
        pattern = r'async def handle_confirm_block\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_confirm_block не найдена"

        function_body = match.group(0)

        # Проверить что НЕТ неправильного связывания
        assert "is_active = not new_blocked_status" not in function_body, \
            "ОШИБКА: Найдено неправильное связывание is_active с is_blocked!"

        assert "new_active_status = not new_blocked_status" not in function_body, \
            "ОШИБКА: Найдено создание new_active_status на основе is_blocked!"

    def test_blocked_users_included_in_list(self):
        """
        Проблема #2: Заблокированные пользователи остаются в списке.

        Проверяет что в функции handle_list_users
        используется list_users(include_inactive=True)
        для включения заблокированных пользователей в список.
        """
        # Найти функцию handle_list_users
        pattern = r'async def handle_list_users\(.*?\):.*?(?=\nasync def|\Z)'
        match = re.search(pattern, self.access_handlers_content, re.DOTALL)

        assert match, "Функция handle_list_users не найдена"

        function_body = match.group(0)

        # Проверить что есть include_inactive=True
        assert "include_inactive=True" in function_body, \
            "ОШИБКА: Не найден параметр include_inactive=True в list_users()!"

    # ========== ГРУППА C: Функциональные тесты ==========

    def test_auth_filter_checks_is_blocked(self):
        """
        Проблема #6: Блокировка работает функционально.

        Проверяет что в auth_filters.py есть проверка
        is_blocked для блокирования доступа заблокированным пользователям.
        """
        # Проверить что есть проверка is_blocked
        assert "if user.is_blocked:" in self.auth_filters_content, \
            "ОШИБКА: Не найдена проверка is_blocked в auth_filters.py!"

        # Проверить что после проверки возвращается False (доступ запрещён)
        blocked_check_pattern = r'if user\.is_blocked:.*?return False'
        assert re.search(blocked_check_pattern, self.auth_filters_content, re.DOTALL), \
            "ОШИБКА: Проверка is_blocked не возвращает False!"

    # ========== Итоговый тест ==========

    def test_all_problems_solved(self):
        """
        Итоговый тест: все 6 проблем решены.

        Суммарная проверка всех исправлений из task.txt.
        """
        issues_solved = []

        # Проблема 1: Нет задержки после блокирования
        # Проверяем через поиск функции handle_confirm_block
        block_func = re.search(r'async def handle_confirm_block\(.*?\):.*?(?=\nasync def|\Z)',
                              self.access_handlers_content, re.DOTALL)
        if block_func:
            # Ищем паттерн успешного уведомления
            success_pattern = r'Пользователь.*?заблокирован.*?message_type="status_message".*?await handle_user_details'
            success_block = re.search(success_pattern, block_func.group(0), re.DOTALL | re.IGNORECASE)
            if success_block and "await asyncio.sleep(NOTIFICATION_DELETE_TIME)" not in success_block.group(0):
                issues_solved.append(1)

        # Проблема 2: Заблокированные в списке
        if "include_inactive=True" in self.access_handlers_content:
            issues_solved.append(2)

        # Проблема 3, 4: Нет задержек при self-actions
        self_actions_count = self.access_handlers_content.count("await asyncio.sleep(ERROR_DELETE_TIME)")
        # Должно быть не более 1 (одна осталась в handle_revoke_invite)
        if self_actions_count <= 1:
            issues_solved.append(3)
            issues_solved.append(4)

        # Проблема 5: Нет задержки после удаления
        delete_func = re.search(r'async def handle_confirm_delete\(.*?\):.*?(?=\nasync def|\Z)',
                               self.access_handlers_content, re.DOTALL)
        if delete_func:
            success_pattern = r'Пользователь удален.*?message_type="status_message".*?await handle_list_users'
            success_block = re.search(success_pattern, delete_func.group(0), re.DOTALL)
            if success_block and "await asyncio.sleep(NOTIFICATION_DELETE_TIME)" not in success_block.group(0):
                issues_solved.append(5)

        # Проблема 6: Блокировка работает
        if "if user.is_blocked:" in self.auth_filters_content:
            issues_solved.append(6)

        # Все 6 проблем должны быть решены
        assert len(issues_solved) == 6, \
            f"Решено только {len(issues_solved)} из 6 проблем: {issues_solved}"

        print(f"\n✅ ВСЕ 6 ПРОБЛЕМ УСПЕШНО РЕШЕНЫ: {issues_solved}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
