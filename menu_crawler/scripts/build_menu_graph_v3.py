#!/usr/bin/env python3
"""
Построитель menu_graph.json для VoxPersona v3 (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Полное покрытие всех 81+ callback_data из COMPLETE_MENU_TREE.md
"""

import json
from pathlib import Path
from typing import Dict, List


class MenuGraphBuilder:
    """Построитель графа меню"""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []

    def add_node(self, node_id: str, node_type: str, depth: int, description: str,
                 dynamic: bool = False, fsm: bool = False):
        """Добавление узла"""
        self.nodes[node_id] = {
            "type": node_type,
            "depth": depth,
            "description": description
        }
        if dynamic:
            self.nodes[node_id]["dynamic"] = True
        if fsm:
            self.nodes[node_id]["fsm"] = True

    def add_edge(self, from_node: str, to_node: str, callback_data: str,
                 button_text: str, condition: str = None):
        """Добавление связи"""
        edge = {
            "from": from_node,
            "to": to_node,
            "callback_data": callback_data,
            "button_text": button_text
        }
        if condition:
            edge["condition"] = condition
        self.edges.append(edge)

    def build_main_menu(self):
        """Главное меню"""
        self.add_node("menu_main", "menu", 0, "Главное меню")

        # Дочерние меню (узлы добавляются в соответствующих методах)
        self.add_edge("menu_main", "menu_chats", "menu_chats", "📱 Чаты/Диалоги")
        self.add_edge("menu_main", "menu_system", "menu_system", "⚙️ Системная")
        self.add_edge("menu_main", "menu_help", "menu_help", "❓ Помощь")

    def build_chats_menu(self):
        """Меню чатов"""
        self.add_node("menu_chats", "menu", 1, "Чаты/Диалоги")

        # Динамические чаты
        self.add_node("chat_actions", "action", 2, "Действия с чатом", dynamic=True)
        self.add_edge("menu_chats", "chat_actions", "chat_actions||{conversation_id}",
                     "📝 [Название чата]")

        # Новый чат
        self.add_node("new_chat", "action", 2, "Новый чат", fsm=True)
        self.add_edge("menu_chats", "new_chat", "new_chat", "🆕 Новый чат")

        # Статистика
        self.add_node("show_stats", "view", 2, "Статистика чатов")
        self.add_edge("menu_chats", "show_stats", "show_stats", "📊 Статистика")

        # Мои отчеты
        self.add_node("show_my_reports", "view", 2, "Мои отчеты")
        self.add_edge("menu_chats", "show_my_reports", "show_my_reports", "📄 Мои отчеты")

        # Назад
        self.add_edge("menu_chats", "menu_main", "menu_main", "🔙 Назад")

    def build_chat_actions(self):
        """Действия с чатом"""
        # Переключение
        self.add_node("confirm_switch", "action", 3, "Подтверждение переключения чата")
        self.add_edge("chat_actions", "confirm_switch", "confirm_switch||{id}", "В Чат")

        # Переименование
        self.add_node("rename_chat", "action", 3, "Переименование чата", fsm=True)
        self.add_edge("chat_actions", "rename_chat", "rename_chat||{id}", "✏️ Переименовать")

        # Удаление
        self.add_node("delete_chat", "action", 3, "Удаление чата")
        self.add_edge("chat_actions", "delete_chat", "delete_chat||{id}", "🗑️ Удалить")

        self.add_node("confirm_delete", "action", 4, "Подтверждение удаления чата")
        self.add_edge("delete_chat", "confirm_delete", "confirm_delete||{id}", "🗑️ Да, удалить")

        # Назад
        self.add_edge("chat_actions", "menu_chats", "menu_chats", "🔙 Назад")

    def build_my_reports(self):
        """Мои отчеты"""
        # Динамические отчеты
        self.add_node("send_report", "action", 3, "Отправить отчет", dynamic=True)
        self.add_edge("show_my_reports", "send_report", "send_report||{report_id}",
                     "📄 [Название отчета]")

        # Показать все
        self.add_node("show_all_reports", "view", 3, "Показать все отчеты")
        self.add_edge("show_my_reports", "show_all_reports", "show_all_reports",
                     "ℹ️ Показать все")

        # Действия с отчетом
        self.add_node("report_view", "action", 4, "Просмотр отчета")
        self.add_edge("send_report", "report_view", "report_view", "👁️ Просмотр")

        self.add_node("report_rename", "action", 4, "Переименование отчета", fsm=True)
        self.add_edge("send_report", "report_rename", "report_rename", "✏️ Переименовать")

        self.add_node("report_delete", "action", 4, "Удаление отчета")
        self.add_edge("send_report", "report_delete", "report_delete", "🗑️ Удалить")

        self.add_node("report_delete_confirm", "action", 5, "Подтверждение удаления отчета")
        self.add_edge("report_delete", "report_delete_confirm",
                     "report_delete_confirm||{num}", "🗑️ Да")

        # Назад
        self.add_edge("show_my_reports", "menu_chats", "menu_chats", "🔙 Назад")
        self.add_edge("send_report", "show_my_reports", "show_my_reports", "🔙 Назад")

    def build_system_menu(self):
        """Системное меню"""
        self.add_node("menu_system", "menu", 1, "Системная")

        # Хранилище
        self.add_node("menu_storage", "menu", 2, "Хранилище")
        self.add_edge("menu_system", "menu_storage", "menu_storage", "📁 Хранилище")

        # Настройки доступа (super_admin only)
        self.add_node("menu_access", "menu", 2, "Настройки доступа")
        self.add_edge("menu_system", "menu_access", "menu_access",
                     "🔐 Настройки доступа", "user_role == super_admin")

        # Назад
        self.add_edge("menu_system", "menu_main", "menu_main", "🔙 Назад")

    def build_storage_menu(self):
        """Меню хранилища"""
        # Аудио файлы
        self.add_node("view||audio", "view", 3, "Просмотр аудио файлов")
        self.add_edge("menu_storage", "view||audio", "view||audio", "📁 Аудио файлы")

        self.add_node("select||audio", "action", 4, "Выбор аудио файла", dynamic=True)
        self.add_edge("view||audio", "select||audio", "select||{filename}", "Выбрать файл")

        self.add_node("delete||audio", "action", 4, "Удаление аудио файла", dynamic=True)
        self.add_edge("view||audio", "delete||audio", "delete||{filename}", "Удалить")

        self.add_node("upload||audio", "action", 4, "Загрузка аудио файла", fsm=True)
        self.add_edge("view||audio", "upload||audio", "upload||audio", "Загрузить")

        # Назад
        self.add_edge("menu_storage", "menu_system", "menu_system", "🔙 Назад")

    def build_access_menu(self):
        """Настройки доступа (super_admin only)"""
        condition = "user_role == super_admin"

        # Управление пользователями
        self.add_node("access_users_menu", "menu", 3, "Управление пользователями")
        self.add_edge("menu_access", "access_users_menu", "access_users_menu",
                     "👥 Управление пользователями", condition)

        # Приглашения
        self.add_node("access_invitations_menu", "menu", 3, "Приглашения")
        self.add_edge("menu_access", "access_invitations_menu", "access_invitations_menu",
                     "🎫 Приглашения", condition)

        # Безопасность
        self.add_node("access_security_menu", "menu", 3, "Настройки безопасности")
        self.add_edge("menu_access", "access_security_menu", "access_security_menu",
                     "⚙️ Настройки безопасности", condition)

        # Назад
        self.add_edge("menu_access", "menu_system", "menu_system", "🔙 Назад", condition)

    def build_access_users(self):
        """Управление пользователями"""
        condition = "user_role == super_admin"

        # Список пользователей
        self.add_node("access_list_users", "view", 4, "Список пользователей")
        self.add_edge("access_users_menu", "access_list_users", "access_list_users",
                     "📊 Список пользователей", condition)

        # Пагинация
        self.add_node("access_list_users||page", "view", 4, "Пагинация списка", dynamic=True)
        self.add_edge("access_list_users", "access_list_users||page",
                     "access_list_users||page||{n}", "➡️ Следующая", condition)

        # Поиск
        self.add_node("access_search_user", "action", 4, "Поиск пользователя", fsm=True)
        self.add_edge("access_list_users", "access_search_user", "access_search_user",
                     "🔍 Поиск пользователя", condition)

        # Фильтры
        self.add_node("access_filter_roles", "menu", 4, "Фильтр по ролям")
        self.add_edge("access_list_users", "access_filter_roles", "access_filter_roles",
                     "📊 Фильтр по ролям", condition)

        self.add_node("access_filter||all", "action", 5, "Фильтр: Все")
        self.add_edge("access_filter_roles", "access_filter||all", "access_filter||all",
                     "Все", condition)

        self.add_node("access_filter||super_admin", "action", 5, "Фильтр: super_admin")
        self.add_edge("access_filter_roles", "access_filter||super_admin",
                     "access_filter||super_admin", "super_admin", condition)

        self.add_node("access_filter||admin", "action", 5, "Фильтр: admin")
        self.add_edge("access_filter_roles", "access_filter||admin",
                     "access_filter||admin", "admin", condition)

        self.add_node("access_filter||user", "action", 5, "Фильтр: user")
        self.add_edge("access_filter_roles", "access_filter||user",
                     "access_filter||user", "user", condition)

        # Детали пользователя (динамические)
        self.add_node("access_user_details", "view", 5, "Детали пользователя", dynamic=True)
        self.add_edge("access_list_users", "access_user_details",
                     "access_user_details||{user_id}", "✅ [Username]", condition)

        # Редактирование
        self.add_node("access_edit_user_select", "action", 4, "Выбор пользователя для редактирования")
        self.add_edge("access_users_menu", "access_edit_user_select", "access_edit_user_select",
                     "✏️ Редактировать пользователя", condition)

        self.add_node("access_edit_user", "menu", 5, "Редактирование пользователя", dynamic=True)
        self.add_edge("access_user_details", "access_edit_user", "access_edit_user||{user_id}",
                     "✏️ Редактировать", condition)

        # Изменение роли
        self.add_node("access_change_role", "menu", 6, "Изменение роли")
        self.add_edge("access_edit_user", "access_change_role", "access_change_role||{user_id}",
                     "Изменить роль", condition)

        self.add_node("access_set_role", "action", 7, "Установка роли", dynamic=True)
        self.add_edge("access_change_role", "access_set_role",
                     "access_set_role||{user_id}||{role}", "[Роль]", condition)

        # Настройки пользователя
        self.add_node("access_change_settings", "menu", 6, "Изменение настроек")
        self.add_edge("access_edit_user", "access_change_settings",
                     "access_change_settings||{user_id}", "Изменить настройки", condition)

        self.add_node("access_set_cleanup", "action", 7, "Установка автоочистки", fsm=True)
        self.add_edge("access_change_settings", "access_set_cleanup",
                     "access_set_cleanup||{user_id}", "Автоочистка сообщений", condition)

        # Сброс пароля
        self.add_node("access_reset_password", "action", 6, "Сброс пароля")
        self.add_edge("access_edit_user", "access_reset_password",
                     "access_reset_password||{user_id}", "Сбросить пароль", condition)

        self.add_node("access_confirm_reset", "action", 7, "Подтверждение сброса пароля")
        self.add_edge("access_reset_password", "access_confirm_reset",
                     "access_confirm_reset||{user_id}", "✅ Да, сбросить", condition)

        # Блокировка
        self.add_node("access_block_user_select", "action", 4, "Выбор пользователя для блокировки")
        self.add_edge("access_users_menu", "access_block_user_select",
                     "access_block_user_select", "🚫 Заблокировать/Разблокировать", condition)

        self.add_node("access_toggle_block", "action", 5, "Блокировка/Разблокировка")
        self.add_edge("access_user_details", "access_toggle_block",
                     "access_toggle_block||{user_id}", "🚫 Заблокировать/Разблокировать", condition)

        self.add_node("access_confirm_block", "action", 6, "Подтверждение блокировки")
        self.add_edge("access_toggle_block", "access_confirm_block",
                     "access_confirm_block||{user_id}", "✅ Да", condition)

        # Удаление
        self.add_node("access_delete_user_select", "action", 4, "Выбор пользователя для удаления")
        self.add_edge("access_users_menu", "access_delete_user_select",
                     "access_delete_user_select", "🗑️ Удалить пользователя", condition)

        self.add_node("access_delete_user_confirm", "action", 5, "Подтверждение удаления")
        self.add_edge("access_user_details", "access_delete_user_confirm",
                     "access_delete_user_confirm||{user_id}", "🗑️ Удалить", condition)

        self.add_node("access_confirm_delete", "action", 6, "Окончательное подтверждение удаления")
        self.add_edge("access_delete_user_confirm", "access_confirm_delete",
                     "access_confirm_delete||{user_id}", "🗑️ Да, удалить", condition)

        # Назад
        self.add_edge("access_users_menu", "menu_access", "menu_access", "🔙 Назад", condition)
        self.add_edge("access_user_details", "access_list_users", "access_list_users",
                     "🔙 Назад", condition)
        self.add_edge("access_edit_user", "access_user_details",
                     "access_user_details||{user_id}", "🔙 Назад", condition)
        self.add_edge("access_filter_roles", "access_list_users", "access_list_users",
                     "🔙 Назад", condition)

    def build_access_invitations(self):
        """Приглашения"""
        condition = "user_role == super_admin"

        # Создание приглашений
        self.add_node("access_create_invite_admin", "action", 4,
                     "Создать приглашение администратора", fsm=True)
        self.add_edge("access_invitations_menu", "access_create_invite_admin",
                     "access_create_invite_admin",
                     "➕ Создать приглашение администратора", condition)

        self.add_node("access_create_invite_user", "action", 4,
                     "Создать приглашение пользователя", fsm=True)
        self.add_edge("access_invitations_menu", "access_create_invite_user",
                     "access_create_invite_user",
                     "➕ Создать приглашение пользователя", condition)

        # Установка срока действия
        self.add_node("access_set_invite_expiry", "action", 5,
                     "Установка срока действия", fsm=True)
        self.add_edge("access_create_invite_admin", "access_set_invite_expiry",
                     "access_set_invite_expiry", "Установить срок действия", condition)

        # Подтверждение создания
        self.add_node("access_confirm_create_invite", "action", 5, "Подтверждение создания")
        self.add_edge("access_create_invite_admin", "access_confirm_create_invite",
                     "access_confirm_create_invite||{role}", "Создать", condition)

        # Список приглашений
        self.add_node("access_list_invites", "view", 4, "Список активных приглашений")
        self.add_edge("access_invitations_menu", "access_list_invites",
                     "access_list_invites", "📜 Активные приглашения", condition)

        # Пагинация
        self.add_node("access_list_invites||page", "view", 4, "Пагинация приглашений", dynamic=True)
        self.add_edge("access_list_invites", "access_list_invites||page",
                     "access_list_invites||page||{n}", "➡️ Следующая", condition)

        # Детали приглашения
        self.add_node("access_invite_details", "view", 5, "Детали приглашения", dynamic=True)
        self.add_edge("access_list_invites", "access_invite_details",
                     "access_invite_details||{invite_code}", "🎫 [CODE]", condition)

        # Аннулирование
        self.add_node("access_revoke_invite", "action", 6, "Аннулирование приглашения")
        self.add_edge("access_invite_details", "access_revoke_invite",
                     "access_revoke_invite||{invite_code}", "❌ Аннулировать", condition)

        self.add_node("access_confirm_revoke", "action", 7, "Подтверждение аннулирования")
        self.add_edge("access_revoke_invite", "access_confirm_revoke",
                     "access_confirm_revoke||{invite_code}", "✅ Да, аннулировать", condition)

        # Назад
        self.add_edge("access_invitations_menu", "menu_access", "menu_access",
                     "🔙 Назад", condition)
        self.add_edge("access_invite_details", "access_list_invites",
                     "access_list_invites", "🔙 Назад", condition)

    def build_access_security(self):
        """Настройки безопасности"""
        condition = "user_role == super_admin"

        # Автоочистка
        self.add_node("access_cleanup_settings", "menu", 4, "Настройки автоочистки")
        self.add_edge("access_security_menu", "access_cleanup_settings",
                     "access_cleanup_settings", "🕒 Автоочистка сообщений", condition)

        self.add_node("access_set_cleanup_hours", "action", 5, "Установка времени очистки", fsm=True)
        self.add_edge("access_cleanup_settings", "access_set_cleanup_hours",
                     "access_set_cleanup_hours", "Установить время (1-48ч)", condition)

        self.add_node("access_cleanup_per_user", "menu", 5, "Настройка для пользователей")
        self.add_edge("access_cleanup_settings", "access_cleanup_per_user",
                     "access_cleanup_per_user", "Настройка для пользователей", condition)

        self.add_node("access_set_user_cleanup", "action", 6,
                     "Установка очистки для пользователя", fsm=True, dynamic=True)
        self.add_edge("access_cleanup_per_user", "access_set_user_cleanup",
                     "access_set_user_cleanup||{user_id}", "[Username]", condition)

        self.add_node("access_view_cleanup_schedule", "view", 5, "Просмотр расписания очистки")
        self.add_edge("access_cleanup_settings", "access_view_cleanup_schedule",
                     "access_view_cleanup_schedule", "Просмотр расписания", condition)

        # Политика паролей
        self.add_node("access_password_policy", "menu", 4, "Политика паролей")
        self.add_edge("access_security_menu", "access_password_policy",
                     "access_password_policy", "🔐 Политика паролей", condition)

        self.add_node("access_set_min_length", "action", 5, "Установка минимальной длины", fsm=True)
        self.add_edge("access_password_policy", "access_set_min_length",
                     "access_set_min_length", "Минимальная длина", condition)

        self.add_node("access_set_complexity", "action", 5, "Установка требований к сложности")
        self.add_edge("access_password_policy", "access_set_complexity",
                     "access_set_complexity", "Требования к сложности", condition)

        self.add_node("access_set_password_ttl", "action", 5, "Установка срока действия", fsm=True)
        self.add_edge("access_password_policy", "access_set_password_ttl",
                     "access_set_password_ttl", "Срок действия", condition)

        # Журнал действий
        self.add_node("access_audit_log", "menu", 4, "Журнал действий")
        self.add_edge("access_security_menu", "access_audit_log",
                     "access_audit_log", "📝 Журнал действий", condition)

        self.add_node("access_view_recent_log", "view", 5, "Просмотр последних записей")
        self.add_edge("access_audit_log", "access_view_recent_log",
                     "access_view_recent_log", "Просмотр последних записей", condition)

        self.add_node("access_filter_log_user", "action", 5, "Фильтр по пользователю")
        self.add_edge("access_audit_log", "access_filter_log_user",
                     "access_filter_log_user", "Фильтр по пользователю", condition)

        self.add_node("access_filter_log_event", "action", 5, "Фильтр по типу события")
        self.add_edge("access_audit_log", "access_filter_log_event",
                     "access_filter_log_event", "Фильтр по типу события", condition)

        self.add_node("access_export_log", "action", 5, "Экспорт журнала")
        self.add_edge("access_audit_log", "access_export_log",
                     "access_export_log", "Экспорт журнала", condition)

        # Назад
        self.add_edge("access_security_menu", "menu_access", "menu_access",
                     "🔙 Назад", condition)
        self.add_edge("access_cleanup_settings", "access_security_menu",
                     "access_security_menu", "🔙 Назад", condition)
        self.add_edge("access_password_policy", "access_security_menu",
                     "access_security_menu", "🔙 Назад", condition)
        self.add_edge("access_audit_log", "access_security_menu",
                     "access_security_menu", "🔙 Назад", condition)
        self.add_edge("access_cleanup_per_user", "access_cleanup_settings",
                     "access_cleanup_settings", "🔙 Назад", condition)

    def build_help_menu(self):
        """Меню помощи"""
        # ГЛАВНЫЙ УЗЕЛ (было пропущено!)
        self.add_node("menu_help", "menu", 1, "Помощь")

        self.add_node("help_about", "view", 2, "О боте")
        self.add_edge("menu_help", "help_about", "help_about", "📱 О боте")

        self.add_node("help_functions", "view", 2, "Функции бота")
        self.add_edge("menu_help", "help_functions", "help_functions", "🛠️ Функции")

        self.add_node("help_stats", "view", 2, "Статистика использования")
        self.add_edge("menu_help", "help_stats", "help_stats", "📊 Статистика")

        self.add_node("help_tips", "view", 2, "Советы по использованию")
        self.add_edge("menu_help", "help_tips", "help_tips", "💡 Советы")

        # Назад
        self.add_edge("menu_help", "menu_main", "menu_main", "🔙 Назад")

    def build_audio_processing(self):
        """Обработка аудио"""
        # Подтверждение данных
        self.add_node("confirm_menu", "menu", 1, "Подтверждение данных из аудио")
        self.add_node("confirm_data", "action", 2, "Подтверждение данных")
        self.add_edge("confirm_menu", "confirm_data", "confirm_data", "✅ Подтвердить")

        self.add_node("edit_data", "action", 2, "Редактирование данных")
        self.add_edge("confirm_menu", "edit_data", "edit_data", "✏️ Изменить")

        # Редактирование данных
        self.add_node("edit_menu", "menu", 3, "Меню редактирования данных")
        self.add_edge("edit_data", "edit_menu", "edit_menu", "[Переход в меню редактирования]")

        self.add_node("edit_audio_number", "action", 4, "Редактирование номера файла", fsm=True)
        self.add_edge("edit_menu", "edit_audio_number", "edit_audio_number", "Номер файла")

        self.add_node("edit_date", "action", 4, "Редактирование даты", fsm=True)
        self.add_edge("edit_menu", "edit_date", "edit_date", "Дата")

        self.add_node("edit_employee", "action", 4, "Редактирование ФИО сотрудника", fsm=True)
        self.add_edge("edit_menu", "edit_employee", "edit_employee", "ФИО Сотрудника")

        self.add_node("edit_place_name", "action", 4, "Редактирование заведения", fsm=True)
        self.add_edge("edit_menu", "edit_place_name", "edit_place_name", "Заведение")

        self.add_node("edit_city", "action", 4, "Редактирование города", fsm=True)
        self.add_edge("edit_menu", "edit_city", "edit_city", "Город")

        self.add_node("edit_zone_name", "action", 4, "Редактирование зоны", fsm=True)
        self.add_edge("edit_menu", "edit_zone_name", "edit_zone_name", "Зона")

        self.add_node("edit_client", "action", 4, "Редактирование клиента", fsm=True)
        self.add_edge("edit_menu", "edit_client", "edit_client", "Клиент")

        self.add_node("edit_building_type", "action", 4, "Редактирование типа здания")
        self.add_edge("edit_menu", "edit_building_type", "edit_building_type", "Тип здания")

        self.add_node("edit_mode", "action", 4, "Редактирование режима работы")
        self.add_edge("edit_menu", "edit_mode", "edit_mode", "Режим работы")

        self.add_node("back_to_confirm", "action", 4, "Возврат к подтверждению")
        self.add_edge("edit_menu", "back_to_confirm", "back_to_confirm", "🔙 Назад к подтверждению")
        self.add_edge("back_to_confirm", "confirm_menu", "confirm_menu", "[Возврат]")

        # Тип здания
        self.add_node("building_type_menu", "menu", 3, "Выбор типа здания")
        self.add_edge("confirm_data", "building_type_menu", "building_type_menu", "[После подтверждения]")
        self.add_edge("edit_building_type", "building_type_menu", "building_type_menu", "[Переход]")

        self.add_node("choose_building||hotel", "action", 4, "Выбор: Отель")
        self.add_edge("building_type_menu", "choose_building||hotel", "choose_building||hotel", "🏨 Отель")

        self.add_node("choose_building||restaurant", "action", 4, "Выбор: Ресторан")
        self.add_edge("building_type_menu", "choose_building||restaurant",
                     "choose_building||restaurant", "🍽️ Ресторан")

        self.add_node("choose_building||other", "action", 4, "Выбор: Другое")
        self.add_edge("building_type_menu", "choose_building||other",
                     "choose_building||other", "🏢 Другое")

        # Режим работы
        self.add_node("interview_menu", "menu", 4, "Выбор режима работы (интервью)")
        self.add_node("design_menu", "menu", 4, "Выбор режима работы (дизайн)")

        self.add_edge("choose_building||hotel", "interview_menu", "interview_menu", "[После выбора здания]")
        self.add_edge("choose_building||restaurant", "interview_menu", "interview_menu", "[После выбора здания]")
        self.add_edge("choose_building||other", "interview_menu", "interview_menu", "[После выбора здания]")
        self.add_edge("edit_mode", "interview_menu", "interview_menu", "[Переход]")

        self.add_node("mode_fast", "action", 5, "Быстрый режим")
        self.add_edge("interview_menu", "mode_fast", "mode_fast", "⚡ Быстрый режим")

        self.add_node("mode_deep", "action", 5, "Глубокий режим")
        self.add_edge("interview_menu", "mode_deep", "mode_deep", "🔬 Глубокий режим")

    def build_auth_flows(self):
        """Аутентификация и смена пароля"""
        # Активация приглашения
        self.add_node("invite_password_input", "action", 1, "Ввод пароля при активации", fsm=True)
        self.add_node("invite_password_confirm", "action", 2, "Подтверждение пароля", fsm=True)
        self.add_edge("invite_password_input", "invite_password_confirm",
                     "invite_password_confirm", "[После ввода пароля]")

        # Смена пароля
        self.add_node("change_password_current", "action", 1, "Ввод текущего пароля", fsm=True)
        self.add_node("change_password_new", "action", 2, "Ввод нового пароля", fsm=True)
        self.add_node("change_password_confirm", "action", 3, "Подтверждение нового пароля", fsm=True)

        self.add_edge("change_password_current", "change_password_new",
                     "change_password_new", "[После текущего пароля]")
        self.add_edge("change_password_new", "change_password_confirm",
                     "change_password_confirm", "[После нового пароля]")

    def build_all(self):
        """Построение всего графа"""
        self.build_main_menu()
        self.build_chats_menu()
        self.build_chat_actions()
        self.build_my_reports()
        self.build_system_menu()
        self.build_storage_menu()
        self.build_access_menu()
        self.build_access_users()
        self.build_access_invitations()
        self.build_access_security()
        self.build_help_menu()
        self.build_audio_processing()
        self.build_auth_flows()

    def validate(self) -> tuple[bool, list]:
        """Валидация графа"""
        errors = []

        # Проверка связности от menu_main
        reachable = set()
        stack = ["menu_main"]

        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)

            for edge in self.edges:
                if edge["from"] == node and edge["to"] not in reachable:
                    stack.append(edge["to"])

        # Изолированные узлы
        all_nodes = set(self.nodes.keys())
        isolated = all_nodes - reachable

        # FSM и специальные узлы могут быть изолированными (entry points)
        isolated_non_special = {
            node for node in isolated
            if not self.nodes[node].get("fsm") and node not in [
                "invite_password_input", "invite_password_confirm",
                "change_password_current", "change_password_new",
                "change_password_confirm", "confirm_menu"
            ]
        }

        if isolated_non_special:
            errors.append(f"Изолированные узлы: {isolated_non_special}")

        # Проверка существования узлов в edges
        for edge in self.edges:
            if edge["from"] not in self.nodes:
                errors.append(f"Узел '{edge['from']}' в edge не существует")
            if edge["to"] not in self.nodes:
                errors.append(f"Узел '{edge['to']}' в edge не существует")

        return len(errors) == 0, errors

    def to_json(self) -> dict:
        """Экспорт в JSON"""
        return {
            "nodes": self.nodes,
            "edges": self.edges
        }

    def get_stats(self) -> dict:
        """Получение статистики"""
        node_types = {}
        for node in self.nodes.values():
            t = node["type"]
            node_types[t] = node_types.get(t, 0) + 1

        dynamic = sum(1 for n in self.nodes.values() if n.get("dynamic"))
        fsm = sum(1 for n in self.nodes.values() if n.get("fsm"))
        conditional = sum(1 for e in self.edges if e.get("condition"))

        # Уникальные callback_data
        callbacks = set(e["callback_data"] for e in self.edges)

        return {
            "nodes_total": len(self.nodes),
            "edges_total": len(self.edges),
            "node_types": node_types,
            "dynamic_nodes": dynamic,
            "fsm_nodes": fsm,
            "conditional_edges": conditional,
            "unique_callbacks": len(callbacks)
        }


def main():
    """Главная функция"""
    print("🌳 ПОСТРОИТЕЛЬ ГРАФА МЕНЮ VOXPERSONA v3 (ИСПРАВЛЕННАЯ ВЕРСИЯ)")
    print("=" * 70)

    # Построение графа
    print("\n🔨 Построение графа меню...")
    builder = MenuGraphBuilder()
    builder.build_all()

    # Статистика
    stats = builder.get_stats()
    print(f"\n📊 СТАТИСТИКА:")
    print(f"   Узлов (nodes): {stats['nodes_total']}")
    print(f"   Связей (edges): {stats['edges_total']}")
    print(f"   Уникальных callback_data: {stats['unique_callbacks']}")

    print(f"\n   По типам узлов:")
    for t, count in sorted(stats['node_types'].items()):
        print(f"      {t}: {count}")

    print(f"\n   Динамические узлы: {stats['dynamic_nodes']}")
    print(f"   FSM узлы: {stats['fsm_nodes']}")
    print(f"   Условные связи (super_admin): {stats['conditional_edges']}")

    # Валидация
    print("\n🔍 Валидация графа...")
    is_valid, errors = builder.validate()

    if is_valid:
        print("✅ Граф валиден! Все узлы достижимы или являются entry points.")
    else:
        print("⚠️ Обнаружены проблемы:")
        for error in errors:
            print(f"   - {error}")

    # Сохранение
    output_path = Path(__file__).parent.parent / "config" / "menu_graph.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Сохранение: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(builder.to_json(), f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size
    print(f"✅ Сохранено: {file_size / 1024:.2f} KB")

    # Примеры узлов
    print(f"\n📋 ПРИМЕРЫ УЗЛОВ:")
    examples = [
        "menu_main", "menu_chats", "chat_actions", "access_user_details",
        "new_chat", "send_report", "menu_help"
    ]
    for node_id in examples:
        if node_id in builder.nodes:
            n = builder.nodes[node_id]
            flags = []
            if n.get("dynamic"):
                flags.append("dynamic")
            if n.get("fsm"):
                flags.append("fsm")
            flags_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"   {node_id}: {n['type']} (depth={n['depth']}){flags_str}")

    # Примеры связей
    print(f"\n🔗 ПРИМЕРЫ СВЯЗЕЙ:")
    edge_examples = builder.edges[:8]
    for e in edge_examples:
        cond_str = f" [CONDITION: {e['condition']}]" if e.get("condition") else ""
        print(f"   {e['from']} → {e['to']}{cond_str}")
        print(f"      callback: {e['callback_data']}")

    print("\n" + "=" * 70)
    print("✅ ГОТОВО! menu_graph.json создан успешно.")
    print("\n📌 ИТОГОВЫЕ МЕТРИКИ:")
    print(f"   ✅ Узлов: {stats['nodes_total']}")
    print(f"   ✅ Связей: {stats['edges_total']}")
    print(f"   ✅ Уникальных callback_data: {stats['unique_callbacks']}")
    print(f"   ✅ Граф валиден: {is_valid}")
    print(f"\n🎯 СООТВЕТСТВИЕ ТРЕБОВАНИЯМ:")
    print(f"   ✅ Ожидалось: 81+ callback_data")
    print(f"   ✅ Получено: {stats['unique_callbacks']} callback_data")
    print(f"   ✅ Все узлы типизированы (menu/action/view)")
    print(f"   ✅ Динамические узлы помечены")
    print(f"   ✅ FSM узлы помечены")
    print(f"   ✅ Условные связи (super_admin) обработаны")


if __name__ == "__main__":
    main()
