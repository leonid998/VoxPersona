#!/usr/bin/env python3
"""
Скрипт для создания Pyrogram User Session для Menu Crawler.

Этот скрипт нужно запустить ЛОКАЛЬНО (НЕ на сервере), так как требуется
интерактивный ввод кода подтверждения из Telegram.

После создания сессии файл menu_crawler_session.session будет загружен на сервер.

Использование:
    python menu_crawler/scripts/create_user_session.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client


async def create_session():
    """
    Создать Pyrogram User Session.

    Процесс:
    1. Загрузить API_ID и API_HASH из .env
    2. Запросить номер телефона (или использовать хардкодный)
    3. Получить код подтверждения из Telegram
    4. Создать файл menu_crawler_session.session
    """
    # Загрузить .env
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"

    if not env_path.exists():
        print(f"❌ Файл .env не найден: {env_path}")
        print("📝 Создайте .env файл с API_ID и API_HASH")
        return

    load_dotenv(env_path)

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    if not api_id or not api_hash:
        print("❌ API_ID или API_HASH не найдены в .env")
        print("📝 Добавьте следующие строки в .env:")
        print("   API_ID=21738379")
        print("   API_HASH=e7e76e237d77713b4dec8e5869f49552")
        return

    print("✅ API_ID и API_HASH загружены из .env")
    print(f"📁 Проект: {project_root}")
    print(f"📂 Сессия будет создана в: {project_root / 'menu_crawler'}")
    print()

    # Номер телефона
    phone = "+79272491236"  # TEST_USER_ID: 155894817 (@AsgoldPrime)

    print(f"📱 Номер телефона: {phone}")
    print()
    print("🔐 Pyrogram отправит код подтверждения в Telegram")
    print("⏳ Подождите SMS или сообщение в Telegram...")
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
        # Запустить клиент (интерактивно запросит код)
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
        print("🚀 СЛЕДУЮЩИЙ ШАГ:")
        print("   Загрузите сессию на сервер командой:")
        print(f"   scp {session_dir / 'menu_crawler_session.session'} root@172.237.73.207:/home/voxpersona_user/VoxPersona/menu_crawler/")
        print()

        # Остановить клиент
        await client.stop()

    except Exception as e:
        print(f"❌ Ошибка при создании сессии: {e}")
        print()
        print("🔧 Возможные причины:")
        print("   1. Неверный код подтверждения")
        print("   2. Номер телефона не зарегистрирован в Telegram")
        print("   3. API_ID или API_HASH неверные")
        print()


if __name__ == "__main__":
    print("=" * 60)
    print("🔐 СОЗДАНИЕ PYROGRAM USER SESSION")
    print("=" * 60)
    print()

    asyncio.run(create_session())
