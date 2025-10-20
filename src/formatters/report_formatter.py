"""
Форматтер для маркетинговых отчетов VoxPersona
"""
from typing import Dict, List, Any
from formatters.base_formatter import BaseFormatter


class ReportFormatter(BaseFormatter):
    """Форматирование маркетинговых отчетов в Markdown для .txt файлов"""

    def format(self, report_data: Dict[str, Any]) -> str:
        """
        Генерация Markdown отчета.

        Args:
            report_data: Данные отчета (структура зависит от типа)

        Returns:
            Markdown-форматированный отчет
        """
        # Заголовок
        title = report_data.get('title', 'Маркетинговый отчет')
        md = f"# 📊 {self.escape_markdown(title)}\n\n"

        # Дата создания
        created_at = report_data.get('created_at')
        if created_at:
            timestamp = self.format_timestamp(created_at)
            md += f"**Создан:** {timestamp}\n\n"

        md += f"{self.heavy_separator}\n\n"

        # Основные метрики
        if 'metrics' in report_data:
            md += "## 📈 Основные метрики\n\n"
            metrics = report_data['metrics']

            for key, value in metrics.items():
                label = key.replace('_', ' ').title()
                md += f"- **{label}:** {value}\n"

            md += f"\n{self.line_separator}\n\n"

        # Секции отчета
        if 'sections' in report_data:
            for section in report_data['sections']:
                section_title = section.get('title', 'Раздел')
                md += f"## {self.escape_markdown(section_title)}\n\n"

                content = section.get('content', '')
                md += f"{content}\n\n"

                # Подразделы
                if 'subsections' in section:
                    for subsection in section['subsections']:
                        sub_title = subsection.get('title', '')
                        md += f"### {self.escape_markdown(sub_title)}\n\n"

                        sub_content = subsection.get('content', '')
                        md += f"{sub_content}\n\n"

                md += f"{self.line_separator}\n\n"

        # Выводы
        if 'conclusion' in report_data:
            md += "## 🎯 Выводы\n\n"
            md += f"{report_data['conclusion']}\n\n"

        # Рекомендации
        if 'recommendations' in report_data:
            md += "## 💡 Рекомендации\n\n"

            for idx, rec in enumerate(report_data['recommendations'], 1):
                md += f"{idx}. {rec}\n"

            md += "\n"

        return md

    def format_summary(self, report_data: Dict[str, Any]) -> str:
        """
        Краткое резюме отчета для Telegram.

        Args:
            report_data: Данные отчета

        Returns:
            Markdown-форматированное резюме
        """
        title = report_data.get('title', 'Отчет')
        summary = f"**📊 {self.escape_markdown(title)}**\n\n"

        # Метрики (топ-3)
        if 'metrics' in report_data:
            metrics = report_data['metrics']
            summary += "**Ключевые метрики:**\n"

            for idx, (key, value) in enumerate(list(metrics.items())[:3], 1):
                label = key.replace('_', ' ').title()
                summary += f"{idx}. {label}: {value}\n"

            summary += "\n"

        # Краткие выводы
        if 'conclusion' in report_data:
            conclusion_preview = self.truncate_text(report_data['conclusion'], 150)
            summary += f"**Выводы:** {conclusion_preview}\n\n"

        summary += "📄 **Полный отчет отправлен файлом**"
        return summary
