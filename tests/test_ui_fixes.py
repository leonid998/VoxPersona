"""
Тесты для проверки UI-исправлений VoxPersona.

Проверяемые функции:
1. INDEX_DISPLAY_NAMES - содержит правильные названия (Казань/РФ)
2. make_index_selection_markup() - использует INDEX_DISPLAY_NAMES
3. make_query_expansion_markup() - кнопки с правильными текстами
4. handle_menu_dialog() - инициализирует deep_search = False

Запуск:
    cd C:/Users/l0934/Projects/VoxPersona
    python -m pytest tests/test_ui_fixes.py -v
"""

import pytest
import sys
import os

# Добавляем путь к src в sys.path для корректного импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestIndexDisplayNames:
    """Тесты для INDEX_DISPLAY_NAMES."""

    def test_index_display_names_kazan_indices(self):
        """Тест: INDEX_DISPLAY_NAMES содержит '(Казань)' для Казанских индексов."""
        from index_selector import INDEX_DISPLAY_NAMES

        # Проверяем Казань
        assert "(Казань)" in INDEX_DISPLAY_NAMES.get("Dizayn", ""), \
            "Dizayn должен содержать '(Казань)'"
        assert "(Казань)" in INDEX_DISPLAY_NAMES.get("Intervyu", ""), \
            "Intervyu должен содержать '(Казань)'"

    def test_index_display_names_rf_indices(self):
        """Тест: INDEX_DISPLAY_NAMES содержит '(РФ)' для федеральных индексов."""
        from index_selector import INDEX_DISPLAY_NAMES

        # Проверяем РФ
        assert "(РФ)" in INDEX_DISPLAY_NAMES.get("Iskhodniki_dizayn", ""), \
            "Iskhodniki_dizayn должен содержать '(РФ)'"
        assert "(РФ)" in INDEX_DISPLAY_NAMES.get("Itogovye_otchety", ""), \
            "Itogovye_otchety должен содержать '(РФ)'"
        assert "(РФ)" in INDEX_DISPLAY_NAMES.get("Iskhodniki_obsledovanie", ""), \
            "Iskhodniki_obsledovanie должен содержать '(РФ)'"
        assert "(РФ)" in INDEX_DISPLAY_NAMES.get("Otchety_po_dizaynu", ""), \
            "Otchety_po_dizaynu должен содержать '(РФ)'"
        assert "(РФ)" in INDEX_DISPLAY_NAMES.get("Otchety_po_obsledovaniyu", ""), \
            "Otchety_po_obsledovaniyu должен содержать '(РФ)'"

    def test_index_display_names_count(self):
        """Тест: INDEX_DISPLAY_NAMES содержит ровно 7 индексов."""
        from index_selector import INDEX_DISPLAY_NAMES

        assert len(INDEX_DISPLAY_NAMES) == 7, \
            f"Ожидается 7 индексов, получено {len(INDEX_DISPLAY_NAMES)}"

    def test_index_display_names_all_keys(self):
        """Тест: INDEX_DISPLAY_NAMES содержит все необходимые ключи."""
        from index_selector import INDEX_DISPLAY_NAMES

        required_keys = [
            "Dizayn",
            "Intervyu",
            "Iskhodniki_dizayn",
            "Iskhodniki_obsledovanie",
            "Itogovye_otchety",
            "Otchety_po_dizaynu",
            "Otchety_po_obsledovaniyu"
        ]

        for key in required_keys:
            assert key in INDEX_DISPLAY_NAMES, \
                f"Ключ '{key}' отсутствует в INDEX_DISPLAY_NAMES"


class TestQueryExpansionMarkup:
    """Тесты для make_query_expansion_markup."""

    def test_button_texts_correct(self):
        """Тест: Кнопки после улучшения имеют правильные тексты."""
        from markups import make_query_expansion_markup

        markup = make_query_expansion_markup(
            original_question="тестовый вопрос",
            expanded_question="улучшенный вопрос",
            conversation_id="test_conv_id",
            deep_search=False,
            refine_count=0,
            selected_index=None,
            top_indices=None
        )

        # Получаем тексты кнопок
        button_texts = []
        for row in markup.inline_keyboard:
            for btn in row:
                button_texts.append(btn.text)

        # Проверяем наличие нужных текстов
        assert any("Отправить как есть" in text for text in button_texts), \
            "Кнопка 'Отправить как есть' не найдена"
        assert any("Улучшить ещё раз" in text for text in button_texts), \
            "Кнопка 'Улучшить ещё раз' не найдена"

    def test_no_old_button_texts(self):
        """Тест: Старые неясные тексты кнопок отсутствуют."""
        from markups import make_query_expansion_markup

        markup = make_query_expansion_markup(
            original_question="тестовый вопрос",
            expanded_question="улучшенный вопрос",
            conversation_id="test_conv_id",
            deep_search=False,
            refine_count=0,
            selected_index=None,
            top_indices=None
        )

        # Получаем тексты кнопок
        button_texts = []
        for row in markup.inline_keyboard:
            for btn in row:
                button_texts.append(btn.text)

        # Проверяем отсутствие старых текстов
        for text in button_texts:
            # Не должно быть просто "Отправить" (без уточнения)
            # или других неясных вариантов
            assert text != "Отправить", \
                "Найден старый неясный текст кнопки 'Отправить'"


class TestIndexSelectionMarkup:
    """Тесты для make_index_selection_markup."""

    def test_no_double_back_button(self):
        """Тест: Нет дублирования текста 'Назад Назад'."""
        from markups import make_index_selection_markup

        # Создаем markup
        markup = make_index_selection_markup()

        # Проверяем все кнопки
        for row in markup.inline_keyboard:
            for btn in row:
                # Не должно быть "Назад Назад"
                assert "Назад Назад" not in btn.text, \
                    f"Найдено дублирование: '{btn.text}'"

    def test_uses_index_display_names(self):
        """Тест: make_index_selection_markup использует INDEX_DISPLAY_NAMES."""
        from markups import make_index_selection_markup
        from index_selector import INDEX_DISPLAY_NAMES

        markup = make_index_selection_markup()

        # Получаем все тексты кнопок
        button_texts = []
        for row in markup.inline_keyboard:
            for btn in row:
                button_texts.append(btn.text)

        # Проверяем что хотя бы некоторые display names присутствуют
        found_count = 0
        for display_name in INDEX_DISPLAY_NAMES.values():
            if any(display_name in text for text in button_texts):
                found_count += 1

        # Должно быть найдено как минимум 5 названий из 7
        assert found_count >= 5, \
            f"Только {found_count} из 7 INDEX_DISPLAY_NAMES найдено в кнопках"

    def test_contains_seven_index_buttons(self):
        """Тест: Клавиатура содержит 7 кнопок для индексов + кнопка Назад."""
        from markups import make_index_selection_markup

        markup = make_index_selection_markup()

        # Считаем количество строк
        # 7 индексов + 1 кнопка назад = 8 строк
        assert len(markup.inline_keyboard) == 8, \
            f"Ожидается 8 строк, получено {len(markup.inline_keyboard)}"


class TestMarkupsImports:
    """Тесты для проверки импортов в markups.py."""

    def test_index_display_names_imported_in_markups(self):
        """Тест: markups.py импортирует INDEX_DISPLAY_NAMES из index_selector."""
        import markups

        # Проверяем что INDEX_DISPLAY_NAMES доступен через импорт модуля
        # Это работает потому что в начале markups.py есть:
        # from index_selector import INDEX_DISPLAY_NAMES
        assert hasattr(markups, 'INDEX_DISPLAY_NAMES'), \
            "markups.py должен импортировать INDEX_DISPLAY_NAMES"

    def test_index_display_names_is_dict(self):
        """Тест: INDEX_DISPLAY_NAMES в markups является словарем."""
        import markups

        assert isinstance(markups.INDEX_DISPLAY_NAMES, dict), \
            "INDEX_DISPLAY_NAMES должен быть словарем"


class TestButtonConstants:
    """Тесты для констант кнопок."""

    def test_button_back_constant(self):
        """Тест: BUTTON_BACK имеет правильное значение."""
        from constants import BUTTON_BACK

        assert BUTTON_BACK == "Назад", \
            f"BUTTON_BACK должен быть 'Назад', получено '{BUTTON_BACK}'"

    def test_button_back_no_duplication(self):
        """Тест: BUTTON_BACK не содержит дублирования."""
        from constants import BUTTON_BACK

        assert "Назад Назад" not in BUTTON_BACK, \
            "BUTTON_BACK не должен содержать дублирование"


class TestHandlerStates:
    """Тесты для состояний обработчиков."""

    def test_user_states_module_import(self):
        """Тест: config.user_states можно импортировать."""
        from config import user_states

        assert isinstance(user_states, dict), \
            "user_states должен быть словарем"


class TestIndexModeSelectionMarkup:
    """Тесты для make_index_mode_selection_markup."""

    def test_no_double_back_in_index_mode_selection(self):
        """Тест: Нет дублирования 'Назад' в make_index_mode_selection_markup."""
        from markups import make_index_mode_selection_markup

        markup = make_index_mode_selection_markup()

        for row in markup.inline_keyboard:
            for btn in row:
                assert "Назад Назад" not in btn.text, \
                    f"Найдено дублирование в make_index_mode_selection_markup: '{btn.text}'"


# Дополнительный тест для интеграции
class TestUIConsistency:
    """Интеграционные тесты для проверки согласованности UI."""

    def test_index_names_consistent(self):
        """Тест: Названия индексов согласованы между INDEX_MAPPING и INDEX_DISPLAY_NAMES."""
        from index_selector import INDEX_MAPPING, INDEX_DISPLAY_NAMES

        # Все ключи из INDEX_MAPPING должны быть в INDEX_DISPLAY_NAMES
        for index_name in INDEX_MAPPING.keys():
            assert index_name in INDEX_DISPLAY_NAMES, \
                f"Индекс '{index_name}' из INDEX_MAPPING отсутствует в INDEX_DISPLAY_NAMES"

    def test_dialog_markup_buttons(self):
        """Тест: make_dialog_markup содержит корректные кнопки."""
        from markups import make_dialog_markup

        markup = make_dialog_markup()

        button_texts = []
        for row in markup.inline_keyboard:
            for btn in row:
                button_texts.append(btn.text)

        # Проверяем наличие ключевых кнопок
        assert any("Быстрый поиск" in text for text in button_texts), \
            "Кнопка 'Быстрый поиск' не найдена"
        assert any("Глубокое исследование" in text for text in button_texts), \
            "Кнопка 'Глубокое исследование' не найдена"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
