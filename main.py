import os
import json
import asyncio
import gspread
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Достаём JSON из переменной окружения (Railway Variable)
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Укажите сюда ID разрешённого отправителя (пока оставим None, чтобы получить ID)
ALLOWED_SENDER_ID = None  # временно

@dp.message()
async def save_message(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    text = message.text or "<нет текста>"

    # Если ALLOWED_SENDER_ID ещё не установлен, выводим ID в чат и в консоль
    global ALLOWED_SENDER_ID
    if ALLOWED_SENDER_ID is None:
        ALLOWED_SENDER_ID = user_id
        logging.info(f"Разрешённый отправитель: {username}, ID: {user_id}")
        await message.answer(f"Ваш ID: {user_id} сохранён для проверки. Теперь отправляйте сообщения ещё раз.")
        return

    # Проверка ID
    if user_id != ALLOWED_SENDER_ID:
        logging.info(f"Игнорируем сообщение от {username}, ID: {user_id}")
        return  # игнорируем чужие сообщения

    # Сохраняем в Google Sheets
    sheet.append_row([username, text])
    await message.answer("✅ Сообщение сохранено в Google Sheets")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
