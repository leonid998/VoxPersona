# 🚀 Быстрый старт: Отправка паролей пользователям

## Шаг 1: Миграция пользователей
```bash
cd C:\Users\l0934\Projects\VoxPersona
python scripts\migrate_users.py
```
**Результат:** Создается `src/auth_data/migration_report.json`

---

## Шаг 2: Отправка паролей
```bash
python scripts\send_passwords_to_telegram.py
```
**Результат:** Создается `src/auth_data/password_delivery_report.json`

---

## Шаг 3: Проверка результатов
```bash
# Посмотреть отчет о доставке
cat src\auth_data\password_delivery_report.json

# Или на Linux/Mac
cat src/auth_data/password_delivery_report.json
```

---

## Шаг 4: Удалить migration_report.json (ВАЖНО!)
```bash
# Если все пароли успешно отправлены:
del src\auth_data\migration_report.json

# На Linux/Mac:
rm src/auth_data/migration_report.json
```

---

## 📨 Что получат пользователи?

Каждый пользователь получит личное сообщение:

```
🔐 Ваш временный пароль для входа в VoxPersona

Пароль: a9Kx2LmNpQr8vZ

⚠️ ВАЖНО:
• Этот пароль действителен до 23 октября 2025, 14:32
• При первом входе потребуется сменить пароль
• Никому не сообщайте пароль

Для входа отправьте команду /start и введите этот пароль при запросе.
```

---

## ⚠️ Возможные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `UserIsBlocked` | Пользователь заблокировал бота | Пользователь должен отправить `/start` боту |
| `PeerIdInvalid` | Некорректный telegram_id | Проверить данные в migration_report.json |
| `FloodWait` | Слишком много запросов | Скрипт автоматически ждет |

---

## 📝 Полная документация
См. `scripts/README_PASSWORD_DELIVERY.md`
