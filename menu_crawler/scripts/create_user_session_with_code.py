#!/usr/bin/env python3
"""
Скрипт для создания Pyrogram User Session с кодом подтверждения.

Использование:
    python menu_crawler/scripts/create_user_session_with_code.py <код>

Пример:
    python menu_crawler/scripts/create_user_session_with_code.py 62874
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client


async def create_session_with_code(verification_code: str):
    """
    Создать Pyrogram User Session с предоставленным кодом подтверждения.

    Args:
        verification_code: Код подтверждения из Telegram (5-6 цифр)
    """
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
    print(f"🔐 Код подтверждения: {verification_code}")
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
        # Запустить клиент с кодом
        print("⏳ Авторизация...")

        async def phone_code_callback():
            return verification_code

        await client.start(phone_code=phone_code_callback)

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
        print("🚀 СЛЕДУЮЩИЙ ШАГ:")
        print("   Загрузите сессию на сервер командой:")
        print(f"   scp {session_dir / 'menu_crawler_session.session'} root@172.237.73.207:/home/voxpersona_user/VoxPersona/menu_crawler/")
        print()

        # Остановить клиент
        await client.stop()

        return True

    except Exception as e:
        print(f"❌ Ошибка при создании сессии: {e}")
        print()
        print("🔧 Возможные причины:")
        print("   1. Неверный код подтверждения")
        print("   2. Код истек (запросите новый)")
        print("   3. Номер телефона не зарегистрирован в Telegram")
        print()

        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔐 СОЗДАНИЕ PYROGRAM USER SESSION")
    print("=" * 60)
    print()

    if len(sys.argv) < 2:
        print("❌ Ошибка: Не указан код подтверждения")
        print()
        print("Использование:")
        print(f"    python {sys.argv[0]} <код>")
        print()
        print("Пример:")
        print(f"    python {sys.argv[0]} 62874")
        sys.exit(1)

    code = sys.argv[1].strip()

    if not code.isdigit() or len(code) < 5:
        print(f"❌ Ошибка: Неверный формат кода: {code}")
        print("   Код должен содержать 5-6 цифр")
        sys.exit(1)

    success = asyncio.run(create_session_with_code(code))

    sys.exit(0 if success else 1)
