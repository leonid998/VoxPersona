#!/usr/bin/env python3
"""
Menu Crawler Main Entry Point

Оркестрирует полный цикл тестирования меню VoxPersona бота:
1. Инициализация Navigator + Pyrogram Client
2. BFS обход всего меню (с throttling + Circuit Breaker)
3. Верификация покрытия (expected vs actual)
4. Генерация отчётов (JSON + Markdown)
5. Cleanup тестовых данных из БД

Использование:
    python -m menu_crawler.src.main

Или на сервере:
    cd /home/voxpersona_user/VoxPersona
    python3 -m menu_crawler.src.main
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавить корневую директорию в PYTHONPATH для импортов
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from menu_crawler.src.navigator import MenuNavigator
from menu_crawler.src.coverage_verifier import CoverageVerifier
from menu_crawler.src.report_builder import ReportBuilder
from menu_crawler.src.utils.cleanup import cleanup_test_user_data
from menu_crawler.src.utils.logging_config import setup_logging, get_logger

# Настроить structured logging
setup_logging()
logger = get_logger("main")


async def main():
    """
    Главная функция - полный цикл Menu Crawler
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = datetime.now()

    logger.info(
        "crawler_session_started",
        session_id=session_id,
        timestamp=start_time.isoformat()
    )

    try:
        # === Шаг 1: Инициализация Navigator ===
        logger.info("step_1_initialization", action="loading_config")

        config_path = project_root / "menu_crawler" / "config"
        navigator = MenuNavigator(config_path=config_path)

        logger.info(
            "navigator_initialized",
            expected_nodes=len(navigator.expected_graph.get('nodes', {})),
            expected_edges=len(navigator.expected_graph.get('edges', []))
        )

        # === Шаг 2: Запуск Pyrogram Client ===
        logger.info("step_2_pyrogram_init", action="starting_client")

        await navigator.init_crawler()

        logger.info(
            "pyrogram_client_started",
            user_id=navigator.user_id,
            username=navigator.username
        )

        # === Шаг 3: BFS обход меню ===
        logger.info("step_3_crawling", action="starting_bfs")

        crawl_start = datetime.now()
        await navigator.crawl()
        crawl_duration = (datetime.now() - crawl_start).total_seconds()

        logger.info(
            "crawl_completed",
            duration_seconds=crawl_duration,
            visited_edges=len(navigator.visited_edges),
            actual_nodes=len(navigator.actual_graph.get('nodes', {}))
        )

        # === Шаг 4: Верификация покрытия ===
        logger.info("step_4_verification", action="comparing_graphs")

        verifier = CoverageVerifier(
            expected_graph=navigator.expected_graph,
            actual_graph=navigator.actual_graph
        )

        metrics = verifier.verify()

        logger.info(
            "verification_completed",
            coverage_percent=metrics['coverage_percent'],
            unreachable_nodes_count=len(metrics['unreachable_nodes']),
            undocumented_nodes_count=len(metrics['undocumented_nodes']),
            status=metrics['status']
        )

        # === Шаг 5: Генерация отчётов ===
        logger.info("step_5_reporting", action="generating_reports")

        # Добавить session info в метрики
        metrics['session_id'] = session_id
        metrics['crawl_duration_seconds'] = crawl_duration
        metrics['test_user_id'] = navigator.user_id

        report_builder = ReportBuilder(metrics=metrics)

        # Создать директорию reports/ если не существует
        reports_dir = project_root / "menu_crawler" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Сохранить JSON отчёт
        json_path = reports_dir / f"report_{session_id}.json"
        report_builder.save_json(json_path)
        logger.info("json_report_saved", path=str(json_path))

        # Сохранить Markdown отчёт
        md_path = reports_dir / f"report_{session_id}.md"
        report_builder.save_markdown(md_path)
        logger.info("markdown_report_saved", path=str(md_path))

        # === Шаг 6: Cleanup тестовых данных ===
        logger.info("step_6_cleanup", action="removing_test_data")

        # Cleanup данных созданных во время этой сессии
        # Используем TEST_USER_ID и timestamp начала сессии
        cleanup_result = cleanup_test_user_data(
            user_id=navigator.user_id,
            created_after=start_time
        )

        logger.info(
            "cleanup_completed",
            total_deleted=cleanup_result['total_deleted'],
            duration_ms=cleanup_result['duration_ms']
        )

        # === Финальная статистика ===
        total_duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            "crawler_session_completed",
            session_id=session_id,
            total_duration_seconds=total_duration,
            status=metrics['status'],
            coverage_percent=metrics['coverage_percent'],
            reports_saved=2,
            cleanup_rows_deleted=cleanup_result['total_deleted']
        )

        # Вернуть 0 при PASS, 1 при PARTIAL/FAIL
        exit_code = 0 if metrics['status'] == 'PASS' else 1

        print(f"\n{'='*60}")
        print(f"✅ Menu Crawler завершён успешно!")
        print(f"{'='*60}")
        print(f"Session ID:      {session_id}")
        print(f"Coverage:        {metrics['coverage_percent']:.1f}%")
        print(f"Status:          {metrics['status']}")
        print(f"Duration:        {total_duration:.1f} сек")
        print(f"Reports:         {json_path}")
        print(f"                 {md_path}")
        print(f"Cleanup:         {cleanup_result['total_deleted']} строк удалено")
        print(f"{'='*60}\n")

        return exit_code

    except KeyboardInterrupt:
        logger.warning("crawler_interrupted_by_user")
        print("\n⚠️  Crawler прерван пользователем (Ctrl+C)")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.error(
            "crawler_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        print(f"\n❌ Ошибка при выполнении crawler: {e}")
        return 1

    finally:
        # Закрыть Pyrogram Client
        if 'navigator' in locals() and hasattr(navigator, 'client'):
            try:
                await navigator.client.stop()
                logger.info("pyrogram_client_stopped")
            except Exception as e:
                logger.warning("failed_to_stop_client", error=str(e))


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
