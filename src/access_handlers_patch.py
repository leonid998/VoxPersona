# Временный файл для проверки синтаксиса исправления

# БЫЛО:
# new_blocked_status = not target_user.is_blocked
# target_user.is_blocked = new_blocked_status
# target_user.updated_at = datetime.now()
# success = auth.storage.update_user(target_user)

# СТАНЕТ:
# Переключить статус блокировки
# СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны
# Блокируем: is_active=False, is_blocked=True
# Разблокируем: is_active=True, is_blocked=False
new_active_status = target_user.is_blocked  # Инверсия: если был заблокирован → делаем активным

# Обновить оба поля синхронно (единый источник истины)
target_user.is_active = new_active_status
target_user.is_blocked = not new_active_status  # Инверсия is_active
target_user.updated_at = datetime.now()
success = auth.storage.update_user(target_user)
