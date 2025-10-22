#!/usr/bin/env python3
"""
Скрипт для создания Pyrogram User Session (принимает код через stdin).

Использование:
    echo "62874" | python menu_crawler/scripts/create_session_stdin.py
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client


# Monkey patch для input() - читать из stdin вместо терминала
original_input = input

def mock_input(prompt=""):
    print(prompt, end='', flush=True)
    line = sys.stdin.readline().strip()
    print(line)  # Echo для видимости
    return line

# Заменить input на mock_input
__builtins__.input = mock_input


async def create_session():
    """Создать Pyrogram User Session."""
    # Загрузить .env
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"

    if not env_path.exists():
        print(f"❌ Файл .env не найден: {env_path}")
        return False

    load_dotenv(env_path)

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    if not api_id or not api_hash:
        print("❌ API_ID или API_HASH не найдены в .env")
        return False

    print("✅ API_ID и API_HASH загружены из .env")
    print(f"📁 Проект: {project_root}")
    print(f"📂 Сессия будет создана в: {project_root / 'menu_crawler'}")
    print()

    # Номер телефона
    phone = "+79272491236"  # TEST_USER_ID: 155894817 (@AsgoldPrime)

    print(f"📱 Номер телефона: {phone}")
    print(f"⏳ Ожидание кода из stdin...")
    print()

    # Создать Pyrogram Client
    session_dir = project_root / "menu_crawler"

    client = Client(
        name="menu_crawler_session",
        api_id=int(api_id),
        api_hash=api_hash,
        workdir=str(session_dir),
        phone_number=phone
    )

    try:
        # Запустить клиент (код будет прочитан из stdin через monkey-patched input)
        await client.start()

        # Получить информацию о пользователе
        me = await client.get_me()

        print()
        print("=" * 60)
        print("✅ СЕССИЯ УСПЕШНО СОЗДАНА!")
        print("=" * 60)
        print(f"👤 Пользователь: {me.first_name} {me.last_name or ''}")
        print(f"🆔 Username: @{me.username}")
        print(f"🔢 Telegram ID: {me.id}")
        print(f"📞 Телефон: {me.phone_number}")
        print()
        print(f"📁 Файл сессии: {session_dir / 'menu_crawler_session.session'}")
        print()

        # Остановить клиент
        await client.stop()

        return True

    except Exception as e:
        print(f"❌ Ошибка при создании сессии: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔐 СОЗДАНИЕ PYROGRAM USER SESSION")
    print("=" * 60)
    print()

    success = asyncio.run(create_session())

    sys.exit(0 if success else 1)
