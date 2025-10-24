#!/bin/bash

###############################################################################
# VoxPersona Automatic Backup Script
# Цель: Ежедневное резервное копирование критичных данных
# Расписание: Запуск в 2:00 AM через cron
# Автор: VoxPersona Team
# Дата создания: 2025-10-24
###############################################################################

set -euo pipefail

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Базовая директория проекта
PROJECT_DIR="/home/voxpersona_user/VoxPersona"

# Директория для хранения backup
BACKUP_DIR="/home/voxpersona_user/backups"

# Имя backup файла с timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="persistent_data_backup_${TIMESTAMP}.tar.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Лог файл
LOG_FILE="${BACKUP_DIR}/backup.log"

# Количество дней хранения backup (по умолчанию 7)
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# Директории для backup (все bind mount volumes из docker-compose.yml)
BACKUP_TARGETS=(
    "telegram_sessions"
    "auth_data"
    "rag_indices"
    "conversations"
    "md_reports"
    "chat_history"
    "logs"
    "data"
)

# Docker named volumes для backup
DOCKER_VOLUMES=(
    "postgres_data"
    "minio_data"
    "minio_certs"
    "pip_cache"
    "huggingface_cache"
)

# Временная директория для экспорта Docker volumes
TEMP_VOLUMES_DIR="${BACKUP_DIR}/temp_volumes_${TIMESTAMP}"

# ============================================================================
# ФУНКЦИИ
# ============================================================================

# Логирование с timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Проверка существования директории
check_directory() {
    local dir=$1
    if [[ ! -d "${PROJECT_DIR}/${dir}" ]]; then
        log "⚠️  WARNING: Директория ${dir} не существует, пропускаем"
        return 1
    fi
    return 0
}

# Вычисление размера директории
get_dir_size() {
    local dir=$1
    du -sh "${PROJECT_DIR}/${dir}" 2>/dev/null | cut -f1 || echo "N/A"
}

# Экспорт Docker named volume в tar архив
export_docker_volume() {
    local volume_name=$1
    local export_path="${TEMP_VOLUMES_DIR}/${volume_name}.tar"

    # Проверка существования volume
    if ! docker volume inspect "${volume_name}" &>/dev/null; then
        log "⚠️  WARNING: Docker volume ${volume_name} не существует, пропускаем"
        return 1
    fi

    log "  📦 Экспорт Docker volume: ${volume_name}"

    # Экспорт volume через временный контейнер
    if docker run --rm \
        -v "${volume_name}:/volume" \
        -v "${TEMP_VOLUMES_DIR}:/backup" \
        alpine \
        tar -cf "/backup/${volume_name}.tar" -C /volume . 2>&1 | tee -a "${LOG_FILE}"; then

        local size=$(du -sh "${export_path}" 2>/dev/null | cut -f1 || echo "N/A")
        log "    ✓ ${volume_name} экспортирован (${size})"
        return 0
    else
        log "    ❌ ERROR: Не удалось экспортировать ${volume_name}"
        return 1
    fi
}

# Экспорт всех Docker volumes
export_all_docker_volumes() {
    log "🐳 Экспорт Docker named volumes..."

    # Создание временной директории
    mkdir -p "${TEMP_VOLUMES_DIR}"

    local exported_count=0
    for volume in "${DOCKER_VOLUMES[@]}"; do
        if export_docker_volume "${volume}"; then
            ((exported_count++))
        fi
    done

    if [[ ${exported_count} -eq 0 ]]; then
        log "⚠️  WARNING: Ни один Docker volume не был экспортирован"
        return 1
    else
        log "✅ Экспортировано Docker volumes: ${exported_count}/${#DOCKER_VOLUMES[@]}"
        return 0
    fi
}

# Очистка временных файлов
cleanup_temp_files() {
    if [[ -d "${TEMP_VOLUMES_DIR}" ]]; then
        log "🧹 Очистка временных файлов..."
        rm -rf "${TEMP_VOLUMES_DIR}"
        log "  ✓ Временные файлы удалены"
    fi
}

# Создание backup директории
create_backup_dir() {
    if [[ ! -d "${BACKUP_DIR}" ]]; then
        log "📁 Создание директории backup: ${BACKUP_DIR}"
        mkdir -p "${BACKUP_DIR}"
    fi
}

# Проверка доступного места на диске
check_disk_space() {
    local available_space=$(df -h "${BACKUP_DIR}" | awk 'NR==2 {print $4}')
    log "💾 Доступное место на диске: ${available_space}"

    # Проверка минимум 5GB свободного места
    local available_kb=$(df -k "${BACKUP_DIR}" | awk 'NR==2 {print $4}')
    if [[ ${available_kb} -lt 5242880 ]]; then
        log "❌ ERROR: Недостаточно места на диске (минимум 5GB требуется)"
        return 1
    fi
    return 0
}

# Создание backup архива
create_backup() {
    log "🚀 Начало создания backup: ${BACKUP_NAME}"

    # Переход в директорию проекта
    cd "${PROJECT_DIR}" || {
        log "❌ ERROR: Не удалось перейти в ${PROJECT_DIR}"
        return 1
    }

    # 1. Формирование списка существующих директорий для backup (bind mounts)
    log "📁 Сбор bind mount директорий..."
    local existing_targets=()
    for target in "${BACKUP_TARGETS[@]}"; do
        if check_directory "${target}"; then
            existing_targets+=("${target}")
            local size=$(get_dir_size "${target}")
            log "  ✓ ${target} (${size})"
        fi
    done

    if [[ ${#existing_targets[@]} -eq 0 ]]; then
        log "⚠️  WARNING: Нет доступных bind mount директорий"
    fi

    # 2. Экспорт Docker named volumes
    export_all_docker_volumes

    # 3. Создание tar.gz архива с bind mounts
    log "📦 Создание архива bind mounts..."
    if [[ ${#existing_targets[@]} -gt 0 ]]; then
        if tar -czf "${BACKUP_PATH}" "${existing_targets[@]}" 2>&1 | tee -a "${LOG_FILE}"; then
            log "  ✓ Bind mounts архивированы"
        else
            log "  ❌ ERROR: Не удалось архивировать bind mounts"
            return 1
        fi
    fi

    # 4. Добавление Docker volumes в архив
    if [[ -d "${TEMP_VOLUMES_DIR}" ]]; then
        log "📦 Добавление Docker volumes в архив..."
        if tar -rf "${BACKUP_PATH%.gz}" -C "${TEMP_VOLUMES_DIR}" . 2>&1 | tee -a "${LOG_FILE}"; then
            log "  ✓ Docker volumes добавлены"
        else
            log "  ⚠️  WARNING: Не удалось добавить Docker volumes"
        fi

        # Перекомпрессия финального архива
        gzip -f "${BACKUP_PATH%.gz}"
    fi

    # 5. Проверка размера финального архива
    if [[ -f "${BACKUP_PATH}" ]]; then
        local backup_size=$(du -sh "${BACKUP_PATH}" | cut -f1)
        log "✅ Backup успешно создан: ${BACKUP_NAME} (${backup_size})"
        return 0
    else
        log "❌ ERROR: Не удалось создать backup архив"
        return 1
    fi
}

# Очистка старых backup (старше RETENTION_DAYS дней)
# ВАЖНО: Всегда оставляет хотя бы один последний backup, даже если он старше RETENTION_DAYS
cleanup_old_backups() {
    log "🧹 Очистка старых backup (старше ${RETENTION_DAYS} дней)..."

    # Найти все backup файлы, отсортированные по дате (новые первые)
    local all_backups
    mapfile -t all_backups < <(find "${BACKUP_DIR}" -name "persistent_data_backup_*.tar.gz" -type f -printf "%T@ %p\n" | sort -rn | cut -d' ' -f2-)

    local total_backups=${#all_backups[@]}

    if [[ ${total_backups} -eq 0 ]]; then
        log "  ℹ️  Нет backup файлов"
        return 0
    fi

    log "  📊 Всего backup файлов: ${total_backups}"

    # Найти старые backup (старше RETENTION_DAYS дней)
    local old_backups
    mapfile -t old_backups < <(find "${BACKUP_DIR}" -name "persistent_data_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -printf "%T@ %p\n" | sort -rn | cut -d' ' -f2-)

    local old_count=${#old_backups[@]}

    if [[ ${old_count} -eq 0 ]]; then
        log "  ✓ Нет старых backup для удаления"
        return 0
    fi

    log "  📊 Старых backup (>${RETENTION_DAYS} дней): ${old_count}"

    # КРИТИЧНО: Если все backup старые, оставить хотя бы последний
    local to_delete_count=0
    if [[ ${old_count} -eq ${total_backups} ]]; then
        log "  ⚠️  Все backup старше ${RETENTION_DAYS} дней!"
        log "  🛡️  Оставляем последний backup для безопасности"
        to_delete_count=$((old_count - 1))
    else
        to_delete_count=${old_count}
    fi

    # Удаление старых backup (кроме последнего)
    local deleted_count=0
    for ((i=1; i<=to_delete_count; i++)); do
        local backup_to_delete="${old_backups[$i]}"
        if [[ -n "${backup_to_delete}" && -f "${backup_to_delete}" ]]; then
            log "  🗑️  Удаление: $(basename "${backup_to_delete}")"
            rm -f "${backup_to_delete}"
            ((deleted_count++))
        fi
    done

    if [[ ${deleted_count} -eq 0 ]]; then
        log "  ✓ Нет backup для удаления (последний сохранен)"
    else
        log "  ✅ Удалено backup файлов: ${deleted_count}"
        log "  🛡️  Сохранено backup файлов: $((total_backups - deleted_count))"
    fi
}

# Вывод статистики backup
show_statistics() {
    log "📊 Статистика backup:"

    # Количество backup файлов
    local total_backups=$(find "${BACKUP_DIR}" -name "persistent_data_backup_*.tar.gz" -type f | wc -l)
    log "  • Всего backup файлов: ${total_backups}"

    # Общий размер всех backup
    local total_size=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1 || echo "N/A")
    log "  • Общий размер: ${total_size}"

    # Последние 5 backup
    log "  • Последние backup:"
    find "${BACKUP_DIR}" -name "persistent_data_backup_*.tar.gz" -type f -printf "%T+ %p\n" | \
        sort -r | head -5 | while read -r line; do
        local date=$(echo "${line}" | awk '{print $1}')
        local file=$(echo "${line}" | awk '{print $2}')
        local size=$(du -sh "${file}" | cut -f1)
        log "    - $(basename "${file}") (${size}, ${date})"
    done
}

# Проверка целостности backup
verify_backup() {
    log "🔍 Проверка целостности backup..."

    if tar -tzf "${BACKUP_PATH}" >/dev/null 2>&1; then
        log "  ✅ Backup архив целостный и читаемый"

        # Список содержимого
        local file_count=$(tar -tzf "${BACKUP_PATH}" | wc -l)
        log "  • Файлов в архиве: ${file_count}"
        return 0
    else
        log "  ❌ ERROR: Backup архив поврежден!"
        return 1
    fi
}

# Основная функция
main() {
    log "════════════════════════════════════════════════════════════════"
    log "🤖 Запуск автоматического backup VoxPersona"
    log "   Режим: Полный backup (bind mounts + Docker volumes)"
    log "   Время хранения: ${RETENTION_DAYS} дней"
    log "════════════════════════════════════════════════════════════════"

    # Шаг 1: Проверка и создание директорий
    create_backup_dir

    # Шаг 2: Проверка доступного места
    if ! check_disk_space; then
        log "❌ FAILED: Backup прерван из-за недостатка места на диске"
        cleanup_temp_files
        exit 1
    fi

    # Шаг 3: Создание backup (bind mounts + Docker volumes)
    if ! create_backup; then
        log "❌ FAILED: Не удалось создать backup"
        cleanup_temp_files
        exit 1
    fi

    # Шаг 4: Очистка временных файлов Docker volumes
    cleanup_temp_files

    # Шаг 5: Проверка целостности
    if ! verify_backup; then
        log "⚠️  WARNING: Backup создан, но проверка целостности не пройдена"
    fi

    # Шаг 6: Очистка старых backup (всегда оставляет последний)
    cleanup_old_backups

    # Шаг 7: Статистика
    show_statistics

    log "════════════════════════════════════════════════════════════════"
    log "✅ Backup успешно завершен!"
    log "   Файл: ${BACKUP_NAME}"
    log "   Путь: ${BACKUP_PATH}"
    log "   Следующий backup: завтра в 02:00"
    log "════════════════════════════════════════════════════════════════"
}

# ============================================================================
# ЗАПУСК
# ============================================================================

# Проверка запуска от имени правильного пользователя
if [[ "${EUID}" -eq 0 ]] && [[ "${USER}" != "root" ]]; then
    log "⚠️  WARNING: Скрипт запущен от root, но рекомендуется запускать от voxpersona_user"
fi

# Trap для обработки ошибок и автоматической очистки
cleanup_on_error() {
    log "❌ ERROR: Backup прерван с ошибкой на линии ${LINENO}"
    cleanup_temp_files
    exit 1
}

trap cleanup_on_error ERR
trap cleanup_temp_files EXIT

# Запуск главной функции
main "$@"

exit 0
