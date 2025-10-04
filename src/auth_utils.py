from pyrogram import Client
from pyrogram.types import Message
from config import PASSWORD
from menus import send_main_menu

async def authorize_user(authorized_users: set, chat_id: int, app: Client):
    authorized_users.add(chat_id)
    await app.send_message(chat_id, "✅ Авторизация успешна!")
    await send_main_menu(chat_id, app)

async def request_password(chat_id: int, app: Client):
    """Отправка дружелюбного сообщения о неверном пароле"""
    message = (
        "🔐 **Доступ закрыт**\n\n"
        "Введённый пароль неверный. Пожалуйста, попробуйте ещё раз.\n\n"
        "💡 *Подсказка:* Убедитесь, что вводите пароль без лишних пробелов"
    )
    await app.send_message(chat_id, message)

async def handle_unauthorized_user(authorized_users: set, message: Message, app: Client):
    if message.text.strip() == PASSWORD:
        await authorize_user(authorized_users, message.chat.id, app)
    else:
        await request_password(message.chat.id, app)
