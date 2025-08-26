from pyrogram import Client
from pyrogram.types import Message
from config import PASSWORD
from menus import send_main_menu

def authorize_user(authorized_users: set, chat_id: int, app: Client):
    authorized_users.add(chat_id)
    app.send_message(chat_id, "✅ Авторизация успешна!")
    send_main_menu(chat_id, app)

def request_password(chat_id: int, app: Client):
    app.send_message(chat_id, "❌ Неверный пароль. Попробуйте снова:")

def handle_unauthorized_user(authorized_users: set, message: Message, app: Client):
    if message.text.strip() == PASSWORD:
        authorize_user(authorized_users, message.chat.id, app)
    else:
        request_password(message.chat.id, app)