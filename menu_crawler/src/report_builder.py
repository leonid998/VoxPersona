"""
Модуль для генерации отчетов о покрытии меню VoxPersona бота.

Генерирует JSON и Markdown отчеты на основе метрик из coverage_verifier.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class ReportBuilder:
    """
    Класс для генерации отчетов о покрытии меню.

    Создает JSON и Markdown отчеты с детальной информацией о покрытии,
    проблемах и UX метриках навигации по меню.
    """

    def __init__(self, metrics: Dict[str, Any], session_info: Optional[Dict[str, Any]] = None):
        """
        Инициализация построителя отчетов.

        Args:
            metrics: Метрики покрытия от coverage_verifier.verify()
            session_info: Опциональная информация о сессии тестирования
                {
                    "session_id": "20251022_153000",
                    "user_id": 155894817,
                    "start_time": "2025-10-22T15:30:00",
                    "end_time": "2025-10-22T15:35:00"
                }
        """
        self.metrics = metrics
        self.session_info = session_info or {}
        self.timestamp = datetime.now().isoformat()

        logger.info(
            "report_building_started",
            session_id=self.session_info.get("session_id"),
            coverage_percent=metrics.get("coverage_percent", 0)
        )

    def build_json(self) -> str:
        """
        Генерация JSON отчета.

        Returns:
            str: JSON строка с детальным отчетом
        """
        issues = self._prioritize_issues()

        report = {
            "timestamp": self.timestamp,
            "session_id": self.session_info.get("session_id", "unknown"),
            "status": self.metrics.get("status", "UNKNOWN"),
            "coverage": {
                "total_expected": self.metrics.get("total_expected", 0),
                "total_visited": self.metrics.get("total_visited", 0),
                "coverage_percent": self.metrics.get("coverage_percent", 0.0)
            },
            "issues": issues,
            "ux_metrics": {
                "max_depth": self.metrics.get("max_depth", 0),
                "deep_nodes_count": len(self.metrics.get("deep_nodes", [])),
                "nodes_without_back_count": len(self.metrics.get("nodes_without_back_button", []))
            }
        }

        # Добавляем информацию о сессии если есть
        if self.session_info:
            report["session_info"] = {
                "user_id": self.session_info.get("user_id"),
                "start_time": self.session_info.get("start_time"),
                "end_time": self.session_info.get("end_time")
            }

        json_str = json.dumps(report, indent=2, ensure_ascii=False)

        logger.info(
            "report_json_built",
            issues_critical=len(issues["critical"]),
            issues_warnings=len(issues["warnings"]),
            issues_info=len(issues["info"])
        )

        return json_str

    def save_json(self, filepath: Path) -> Path:
        """
        Сохранение JSON отчета в файл.

        Args:
            filepath: Путь к файлу для сохранения

        Returns:
            Path: Путь к сохраненному файлу
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        json_content = self.build_json()
        filepath.write_text(json_content, encoding="utf-8")

        logger.info("report_saved_json", filepath=str(filepath), size_bytes=len(json_content))

        return filepath

    def build_markdown(self) -> str:
        """
        Генерация Markdown отчета.

        Returns:
            str: Markdown строка с форматированным отчетом
        """
        issues = self._prioritize_issues()
        status_emoji = self._format_status_emoji(self.metrics.get("status", "UNKNOWN"))
        formatted_time = self._format_timestamp(self.timestamp)

        # Заголовок
        md = ["# 📊 Menu Crawler Report\n"]
        md.append(f"**Дата:** {formatted_time}  ")
        md.append(f"**Статус:** {status_emoji}  ")
        md.append(f"**Session ID:** {self.session_info.get('session_id', 'unknown')}\n")
        md.append("---\n")

        # Покрытие
        md.append("## 📈 Покрытие меню\n")
        md.append("| Метрика | Значение |")
        md.append("|---------|----------|")
        md.append(f"| Всего узлов (ожидается) | {self.metrics.get('total_expected', 0)} |")
        md.append(f"| Посещено узлов | {self.metrics.get('total_visited', 0)} |")

        coverage = self.metrics.get("coverage_percent", 0.0)
        coverage_status = "✅" if coverage == 100 else "⚠️" if coverage >= 90 else "❌"
        md.append(f"| **Coverage** | **{coverage:.1f}%** {coverage_status} |\n")
        md.append("---\n")

        # Критичные проблемы
        critical = issues["critical"]
        md.append(f"## 🔴 Критичные проблемы ({len(critical)})\n")

        if not critical:
            md.append("*Критичных проблем не обнаружено*\n")
        else:
            for issue in critical:
                md.append(f"- `{issue['node']}` - {issue['type']}")

        md.append("---\n")

        # Предупреждения
        warnings = issues["warnings"]
        md.append(f"## 🟡 Предупреждения ({len(warnings)})\n")

        # Инициализация переменных (используются позже в рекомендациях)
        undocumented = [w for w in warnings if w["type"] == "undocumented_node"]
        deep = [w for w in warnings if w["type"] == "deep_node"]
        no_back = [w for w in warnings if w["type"] == "no_back_button"]

        if not warnings:
            md.append("*Предупреждений не обнаружено*\n")
        else:
            # Группировка по типам уже сделана выше

            if undocumented:
                md.append(f"### Недокументированные узлы ({len(undocumented)})")
                for issue in undocumented:
                    md.append(f"- `{issue['node']}` - узел найден в боте, но отсутствует в menu_graph.json\n")

            if deep:
                md.append(f"### Глубокие узлы (>4 кликов) ({len(deep)})")
                for issue in deep:
                    md.append(f"- `{issue['node']}` - глубина {issue.get('depth', '?')} кликов\n")

            if no_back:
                md.append(f"### Узлы без кнопки \"Назад\" ({len(no_back)})")
                for issue in no_back:
                    md.append(f"- `{issue['node']}` - отсутствует навигация назад\n")

        md.append("---\n")

        # UX Метрики
        md.append("## 📐 UX Метрики\n")
        md.append("| Метрика | Значение |")
        md.append("|---------|----------|")
        md.append(f"| Максимальная глубина навигации | {self.metrics.get('max_depth', 0)} кликов |")
        md.append(f"| Узлов глубже 4 уровня | {len(self.metrics.get('deep_nodes', []))} |")
        md.append(f"| Узлов без кнопки \"Назад\" | {len(self.metrics.get('nodes_without_back_button', []))} |\n")
        md.append("---\n")

        # Рекомендации
        md.append("## ✅ Рекомендации\n")

        if coverage == 100:
            md.append("- ✅ Покрытие 100% - все меню доступны")
        elif coverage >= 90:
            md.append(f"- ⚠️ Покрытие {coverage:.1f}% - почти полное, но есть недоступные узлы")
        else:
            md.append(f"- ❌ Покрытие {coverage:.1f}% - требуется проверка недоступных узлов")

        if undocumented:
            md.append("- ⚠️ Обновить menu_graph.json - добавить недокументированные узлы")

        if deep:
            md.append("- ⚠️ Рассмотреть упрощение навигации для глубоких узлов")

        if no_back:
            md.append("- ⚠️ Добавить кнопки \"Назад\" в меню без навигации")

        if not critical and not warnings:
            md.append("- 🎉 Отлично! Проблем не обнаружено\n")

        md.append("\n---\n")
        md.append("*Отчет сгенерирован Menu Crawler v1.0*")

        markdown_content = "\n".join(md)

        logger.info("report_markdown_built", length=len(markdown_content))

        return markdown_content

    def save_markdown(self, filepath: Path) -> Path:
        """
        Сохранение Markdown отчета в файл.

        Args:
            filepath: Путь к файлу для сохранения

        Returns:
            Path: Путь к сохраненному файлу
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        markdown_content = self.build_markdown()
        filepath.write_text(markdown_content, encoding="utf-8")

        logger.info("report_saved_markdown", filepath=str(filepath), size_bytes=len(markdown_content))

        return filepath

    def _prioritize_issues(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Приоритизация проблем по важности.

        Returns:
            dict: Словарь с проблемами по категориям:
                {
                    "critical": [...],
                    "warnings": [...],
                    "info": [...]
                }
        """
        issues = {
            "critical": [],
            "warnings": [],
            "info": []
        }

        # CRITICAL: недоступные узлы (в документации, но нет в боте)
        for node in self.metrics.get("unreachable_nodes", []):
            issues["critical"].append({
                "type": "unreachable_node",
                "node": node,
                "severity": "CRITICAL"
            })

        # WARNING: недокументированные узлы (в боте, но нет в документации)
        for node in self.metrics.get("undocumented_nodes", []):
            issues["warnings"].append({
                "type": "undocumented_node",
                "node": node,
                "severity": "WARNING"
            })

        # WARNING: глубокие узлы (>4 кликов)
        for node, depth in self.metrics.get("deep_nodes", []):
            issues["warnings"].append({
                "type": "deep_node",
                "node": node,
                "depth": depth,
                "severity": "WARNING"
            })

        # WARNING: узлы без кнопки "Назад"
        for node in self.metrics.get("nodes_without_back_button", []):
            issues["warnings"].append({
                "type": "no_back_button",
                "node": node,
                "severity": "WARNING"
            })

        # INFO: неполное покрытие (90-99%)
        coverage = self.metrics.get("coverage_percent", 0)
        if 90 <= coverage < 100:
            issues["info"].append({
                "type": "incomplete_coverage",
                "coverage": coverage,
                "severity": "INFO"
            })

        return issues

    def _format_status_emoji(self, status: str) -> str:
        """
        Форматирование статуса с emoji для Markdown.

        Args:
            status: Статус теста (PASS/PARTIAL/FAIL)

        Returns:
            str: Статус с emoji
        """
        emoji_map = {
            "PASS": "✅ PASS",
            "PARTIAL": "⚠️ PARTIAL",
            "FAIL": "❌ FAIL",
            "UNKNOWN": "❓ UNKNOWN"
        }
        return emoji_map.get(status.upper(), f"❓ {status}")

    def _format_timestamp(self, ts: Optional[str] = None) -> str:
        """
        Форматирование временной метки.

        Args:
            ts: ISO формат времени или None для текущего времени

        Returns:
            str: Форматированная строка "22 октября 2025, 15:35:00"
        """
        if ts:
            dt = datetime.fromisoformat(ts)
        else:
            dt = datetime.now()

        # Русские названия месяцев
        months_ru = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]

        return f"{dt.day} {months_ru[dt.month - 1]} {dt.year}, {dt.strftime('%H:%M:%S')}"


# Пример использования
if __name__ == "__main__":
    import structlog

    # Настройка логирования
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Пример метрик
    example_metrics = {
        "total_expected": 104,
        "total_visited": 104,
        "coverage_percent": 100.0,
        "unreachable_nodes": [],
        "undocumented_nodes": ["menu_new_feature"],
        "max_depth": 5,
        "deep_nodes": [["admin_settings_advanced", 5]],
        "nodes_without_back_button": [],
        "status": "PASS"
    }

    # Пример информации о сессии
    example_session = {
        "session_id": "20251022_153000",
        "user_id": 155894817,
        "start_time": "2025-10-22T15:30:00",
        "end_time": "2025-10-22T15:35:00"
    }

    # Создание отчетов
    builder = ReportBuilder(example_metrics, example_session)

    # JSON отчет
    json_report = builder.build_json()
    print("=== JSON Report ===")
    print(json_report)
    print()

    # Markdown отчет
    md_report = builder.build_markdown()
    print("=== Markdown Report ===")
    print(md_report)
    print()

    # Сохранение отчетов
    output_dir = Path("C:/Users/l0934/Projects/VoxPersona/menu_crawler/reports")

    json_path = builder.save_json(output_dir / "coverage_report.json")
    print(f"✅ JSON отчет сохранен: {json_path}")

    md_path = builder.save_markdown(output_dir / "coverage_report.md")
    print(f"✅ Markdown отчет сохранен: {md_path}")
