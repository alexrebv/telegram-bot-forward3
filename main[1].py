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

@dp.message()
async def save_message(message: Message):
    """Сохраняем входящие сообщения в Google таблицу"""
    user = message.from_user.username or message.from_user.full_name
    text = message.text or "<нет текста>"
    sheet.append_row([user, text])
    await message.answer("✅ Сообщение сохранено в Google Sheets")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
