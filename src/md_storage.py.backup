"""
Модуль для управления архивом MD отчетов.
Реализует сохранение, индексацию и поиск отчетов в формате Markdown.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from config import MD_REPORTS_DIR
from constants import MD_FILE_PREFIX, MD_FILE_EXTENSION, INDEX_FILE_NAME
from utils import count_tokens


@dataclass
class ReportMetadata:
    """Метаданные отчета."""
    file_path: str
    user_id: int
    username: str
    timestamp: str
    question: str
    size_bytes: int
    tokens: int
    search_type: str


class MDStorageManager:
    """Менеджер для управления MD отчетами."""

    def __init__(self):
        self.reports_dir = Path(MD_REPORTS_DIR)
        self.ensure_reports_directory()

    def ensure_reports_directory(self) -> None:
        """Создает директорию отчетов если она не существует."""
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Reports directory ensured: {self.reports_dir}")
        except Exception as e:
            logging.error(f"Failed to create reports directory {self.reports_dir}: {e}")
            raise

    def ensure_user_directory(self, user_id: int) -> Path:
        """Создает директорию пользователя если она не существует."""
        user_dir = self.reports_dir / f"user_{user_id}"
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            return user_dir
        except Exception as e:
            logging.error(f"Failed to create user directory {user_dir}: {e}")
            raise

    def generate_filename(self) -> str:
        """Генерирует уникальное имя файла."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{MD_FILE_PREFIX}_{timestamp}{MD_FILE_EXTENSION}"

    def create_md_content(
        self, 
        content: str, 
        username: str, 
        user_id: int, 
        question: str, 
        search_type: str
    ) -> str:
        """Создает содержимое MD файла согласно шаблону."""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        md_content = f"""# Отчет VoxPersona
**Дата:** {timestamp}
**Пользователь:** @{username} (ID: {user_id})
**Запрос:** {question}
**Тип поиска:** {search_type}

---

{content}
"""
        return md_content

    def save_md_report(
        self, 
        content: str, 
        user_id: int, 
        username: str, 
        question: str, 
        search_type: str
    ) -> Optional[str]:
        """Сохраняет MD отчет и возвращает путь к файлу."""
        try:
            user_dir = self.ensure_user_directory(user_id)
            filename = self.generate_filename()
            file_path = user_dir / filename
            
            # Создаем содержимое MD файла
            md_content = self.create_md_content(content, username, user_id, question, search_type)
            
            # Сохраняем файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Обновляем индекс
            metadata = ReportMetadata(
                file_path=str(file_path.relative_to(self.reports_dir)),
                user_id=user_id,
                username=username,
                timestamp=datetime.now().isoformat(),
                question=question,
                size_bytes=len(md_content.encode('utf-8')),
                tokens=count_tokens(content),
                search_type=search_type
            )
            
            self.update_reports_index(metadata)
            
            logging.info(f"Saved MD report: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logging.error(f"Failed to save MD report: {e}")
            return None

    def load_reports_index(self) -> List[ReportMetadata]:
        """Загружает индекс отчетов."""
        index_path = self.reports_dir / INDEX_FILE_NAME
        
        if not index_path.exists():
            return []
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return [ReportMetadata(**item) for item in data]
        except Exception as e:
            logging.error(f"Failed to load reports index: {e}")
            return []

    def save_reports_index(self, reports: List[ReportMetadata]) -> bool:
        """Сохраняет индекс отчетов."""
        index_path = self.reports_dir / INDEX_FILE_NAME
        
        try:
            data = [asdict(report) for report in reports]
            
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logging.error(f"Failed to save reports index: {e}")
            return False

    def update_reports_index(self, new_report: ReportMetadata) -> bool:
        """Обновляет индекс отчетов, добавляя новый отчет."""
        try:
            reports = self.load_reports_index()
            reports.append(new_report)
            return self.save_reports_index(reports)
        except Exception as e:
            logging.error(f"Failed to update reports index: {e}")
            return False

    def get_user_reports(self, user_id: int, limit: Optional[int] = 10) -> List[ReportMetadata]:
        """Возвращает отчеты пользователя, отсортированные по дате (новые сначала)."""
        try:
            all_reports = self.load_reports_index()
            user_reports = [r for r in all_reports if r.user_id == user_id]
            
            # Сортируем по времени создания (новые сначала)
            user_reports.sort(key=lambda x: x.timestamp, reverse=True)
            
            return user_reports if limit is None else user_reports[:limit]
        except Exception as e:
            logging.error(f"Failed to get user reports: {e}")
            return []

    def get_report_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Возвращает статистику отчетов."""
        try:
            all_reports = self.load_reports_index()
            
            if user_id is not None:
                reports = [r for r in all_reports if r.user_id == user_id]
            else:
                reports = all_reports

            stats = {
                "total_reports": len(reports),
                "total_size_bytes": sum(r.size_bytes for r in reports),
                "total_tokens": sum(r.tokens for r in reports),
                "fast_searches": len([r for r in reports if r.search_type == "fast"]),
                "deep_searches": len([r for r in reports if r.search_type == "deep"]),
            }
            
            if reports:
                stats["avg_size_bytes"] = stats["total_size_bytes"] / len(reports)
                stats["avg_tokens"] = stats["total_tokens"] / len(reports)
            else:
                stats["avg_size_bytes"] = 0
                stats["avg_tokens"] = 0

            return stats
        except Exception as e:
            logging.error(f"Failed to get report stats: {e}")
            return {}

    def get_report_file_path(self, relative_path: str) -> Optional[Path]:
        """Возвращает полный путь к файлу отчета."""
        try:
            full_path = self.reports_dir / relative_path
            if full_path.exists():
                return full_path
            return None
        except Exception as e:
            logging.error(f"Failed to get report file path: {e}")
            return None

    def format_user_reports_for_display(self, user_id: int) -> str:
        """Форматирует список отчетов пользователя для отображения."""
        reports = self.get_user_reports(user_id, limit=10)
        
        if not reports:
            return "📁 **Ваши отчеты:**\n\nУ вас пока нет сохраненных отчетов."

        result = f"📁 **Ваши отчеты (последние {len(reports)}):**\n\n"
        
        for i, report in enumerate(reports, 1):
            timestamp = datetime.fromisoformat(report.timestamp).strftime("%d.%m.%Y %H:%M")
            question_preview = report.question[:60] + "..." if len(report.question) > 60 else report.question
            search_icon = "⚡" if report.search_type == "fast" else "🔍"
            size_kb = report.size_bytes / 1024
            
            result += f"{i}. {search_icon} **{timestamp}**\n"
            result += f"   📝 {question_preview}\n"
            result += f"   📊 {report.tokens:,} токенов, {size_kb:.1f} KB\n\n"

        # Добавляем статистику
        stats = self.get_report_stats(user_id)
        result += f"📈 **Общая статистика:**\n"
        result += f"📄 Всего отчетов: {stats['total_reports']}\n"
        result += f"💾 Общий размер: {stats['total_size_bytes'] / (1024*1024):.2f} MB\n"
        result += f"📝 Всего токенов: {stats['total_tokens']:,}\n"

        return result

    def cleanup_old_reports(self, days_old: int = 30) -> int:
        """Удаляет старые отчеты (старше указанного количества дней)."""
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
            reports = self.load_reports_index()
            
            reports_to_keep = []
            deleted_count = 0
            
            for report in reports:
                report_date = datetime.fromisoformat(report.timestamp).timestamp()
                
                if report_date >= cutoff_date:
                    reports_to_keep.append(report)
                else:
                    # Удаляем файл
                    file_path = self.get_report_file_path(report.file_path)
                    if file_path and file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                        logging.info(f"Deleted old report: {file_path}")

            # Обновляем индекс
            self.save_reports_index(reports_to_keep)
            
            logging.info(f"Cleanup completed: {deleted_count} old reports deleted")
            return deleted_count
            
        except Exception as e:
            logging.error(f"Failed to cleanup old reports: {e}")
            return 0

    def validate_integrity(self) -> Dict[str, Any]:
        """Проверяет целостность архива отчетов."""
        try:
            reports = self.load_reports_index()
            
            result = {
                "total_reports": len(reports),
                "existing_files": 0,
                "missing_files": 0,
                "orphaned_files": 0,
                "missing_file_paths": [],
                "orphaned_file_paths": []
            }
            
            # Проверяем существование файлов из индекса
            for report in reports:
                file_path = self.get_report_file_path(report.file_path)
                if file_path and file_path.exists():
                    result["existing_files"] += 1
                else:
                    result["missing_files"] += 1
                    result["missing_file_paths"].append(report.file_path)
            
            # Ищем файлы без записей в индексе
            indexed_paths = {report.file_path for report in reports}
            
            for user_dir in self.reports_dir.glob("user_*"):
                if user_dir.is_dir():
                    for md_file in user_dir.glob(f"*{MD_FILE_EXTENSION}"):
                        relative_path = str(md_file.relative_to(self.reports_dir))
                        if relative_path not in indexed_paths:
                            result["orphaned_files"] += 1
                            result["orphaned_file_paths"].append(relative_path)
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to validate integrity: {e}")
            return {"error": str(e)}



    def find_orphaned_reports(self, user_id: int) -> List[str]:
        """
        Находит MD отчеты не связанные ни с одним чатом.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список путей к осиротевшим MD файлам
        """
        from conversation_manager import conversation_manager
        
        # Получаем все MD файлы пользователя
        all_reports = self.get_user_reports(user_id, limit=None)
        
        # Получаем все чаты пользователя
        conversations = conversation_manager.list_conversations(user_id)
        
        # Собираем все file_path из всех чатов
        linked_files = set()
        for conv_meta in conversations:
            conv = conversation_manager.load_conversation(user_id, conv_meta.conversation_id)
            if conv:
                for msg in conv.messages:
                    if msg.file_path:
                        linked_files.add(msg.file_path)
        
        # Находим осиротевшие
        orphaned = [
            report.file_path
            for report in all_reports
            if report.file_path not in linked_files
        ]
        
        return orphaned

    def cleanup_orphaned_reports(self, user_id: int) -> int:
        """
        Удаляет осиротевшие MD отчеты.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество удаленных файлов
        """
        orphaned = self.find_orphaned_reports(user_id)
        deleted_count = 0
        
        for file_path in orphaned:
            try:
                full_path = self.get_report_file_path(file_path)
                if full_path and full_path.exists():
                    full_path.unlink()
                    deleted_count += 1
                    logging.info(f"Cleaned up orphaned MD file: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to delete orphaned file {file_path}: {e}")
        
        # Обновляем index.json - удаляем записи об удаленных файлах
        if deleted_count > 0:
            self._remove_from_index(orphaned)
        
        logging.info(f"Cleaned up {deleted_count} orphaned reports for user {user_id}")
        return deleted_count

    def _remove_from_index(self, file_paths: List[str]):
        """Удаляет записи об удаленных файлах из index.json."""
        try:
            index_file = self.reports_dir / INDEX_FILE_NAME
            if not index_file.exists():
                return
            
            with open(index_file, 'r', encoding='utf-8') as f:
                reports = json.load(f)
            
            # Фильтруем удаленные файлы
            file_paths_set = set(file_paths)
            updated_reports = [
                report for report in reports
                if report.get('file_path') not in file_paths_set
            ]
            
            # Сохраняем обновленный индекс
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(updated_reports, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Removed {len(reports) - len(updated_reports)} entries from MD index")
            
        except Exception as e:
            logging.error(f"Failed to update MD index: {e}")



# Создаем глобальный экземпляр менеджера
md_storage_manager = MDStorageManager()