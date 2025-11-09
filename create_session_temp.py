#!/usr/bin/env python3
"""
Скрипт для создания Pyrogram сессии
"""
from pyrogram import Client
import os
from dotenv import load_dotenv

# Загрузить .env
load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

print(f"API_ID: {api_id}")
print(f"API_HASH: {api_hash[:10]}...")
print("\nЗапуск Pyrogram Client...")
print("Введите номер телефона (формат: +79XXXXXXXXX):")

# Создать клиент и запустить интерактивную авторизацию
with Client("test_user_session", api_id=api_id, api_hash=api_hash) as app:
    print("\n✅ Session created successfully!")
    print(f"User ID: {app.me.id}")
    print(f"Username: @{app.me.username if app.me.username else 'N/A'}")
    print(f"First Name: {app.me.first_name}")
    print(f"\nФайл сессии сохранён: test_user_session.session")
