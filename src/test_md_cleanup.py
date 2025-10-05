#!/usr/bin/env python3
"""
Тестовый скрипт для проверки cleanup механизма MD файлов.
"""
import sys
import logging
from pathlib import Path

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Импортируем необходимые модули
from conversation_manager import conversation_manager
from md_storage import md_storage_manager

def test_cleanup_mechanism():
    """Тестирует механизм cleanup MD файлов."""
    
    test_user_id = 999999  # Тестовый пользователь
    
    print("\n" + "="*60)
    print("ТЕСТ: Cleanup механизм MD файлов при удалении чатов")
    print("="*60)
    
    # 1. Проверяем поиск orphaned файлов
    print("\n1. Поиск осиротевших MD файлов...")
    orphaned = md_storage_manager.find_orphaned_reports(test_user_id)
    print(f"   Найдено осиротевших файлов: {len(orphaned)}")
    if orphaned:
        print(f"   Первые 3 файла: {orphaned[:3]}")
    
    # 2. Проверяем функцию cleanup
    print("\n2. Запуск cleanup осиротевших файлов...")
    deleted = md_storage_manager.cleanup_orphaned_reports(test_user_id)
    print(f"   Удалено файлов: {deleted}")
    
    # 3. Проверяем что метод delete_conversation теперь удаляет MD файлы
    print("\n3. Проверка delete_conversation с MD cleanup...")
    
    # Проверяем список чатов
    conversations = conversation_manager.list_conversations(test_user_id)
    print(f"   Всего чатов у пользователя {test_user_id}: {len(conversations)}")
    
    if conversations:
        # Берем первый чат для теста
        test_conv = conversations[0]
        print(f"   Тестовый чат: {test_conv.conversation_id}")
        
        # Загружаем чат и проверяем MD файлы
        conv = conversation_manager.load_conversation(test_user_id, test_conv.conversation_id)
        if conv:
            md_files = [msg.file_path for msg in conv.messages if msg.file_path and msg.sent_as == "file"]
            print(f"   MD файлов в чате: {len(md_files)}")
            
            if md_files:
                print(f"   Первые MD файлы: {md_files[:2]}")
                
                # Удаляем чат
                print(f"\n   Удаление чата {test_conv.conversation_id}...")
                success = conversation_manager.delete_conversation(test_user_id, test_conv.conversation_id)
                
                if success:
                    print("   ✅ Чат успешно удален")
                    
                    # Проверяем что MD файлы также удалены
                    print("\n   Проверка удаления MD файлов...")
                    for file_path in md_files[:2]:  # Проверяем только первые 2
                        exists = Path(file_path).exists()
                        status = "❌ СУЩЕСТВУЕТ" if exists else "✅ УДАЛЕН"
                        print(f"      {status}: {file_path}")
                else:
                    print("   ❌ Ошибка при удалении чата")
            else:
                print("   ℹ️  В чате нет MD файлов для тестирования")
        else:
            print("   ❌ Не удалось загрузить чат")
    else:
        print("   ℹ️  У пользователя нет чатов для тестирования")
    
    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        test_cleanup_mechanism()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
