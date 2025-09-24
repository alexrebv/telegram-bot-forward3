import os
import json
import asyncio
import gspread
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # например, @my_channel_username или -1001234567890

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Google Sheets авторизация
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

@dp.message()
async def save_channel_message(message: Message):
    # Проверяем, что сообщение из нужного канала
    if str(message.chat.id) != str(CHANNEL_ID) and (message.chat.username != CHANNEL_ID):
        return  # игнорируем другие чаты

    # Дата и текст
    date = message.date.strftime("%Y-%m-%d %H:%M:%S")
    text = message.text or "<нет текста>"

    # Имя автора (если бот или группа, используем sender_chat)
    author = message.sender_chat.title if message.sender_chat else (message.from_user.username or message.from_user.full_name)

    # Сохраняем в Google Sheets
    sheet.append_row([date, author, text])
    logging.info(f"Сохранено сообщение: {author} | {text}")

async def main():
    logging.info("Бот запущен для чтения канала")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
