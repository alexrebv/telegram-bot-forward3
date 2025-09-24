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

# Подключение к Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

@dp.message()
async def save_group_message(message: Message):
    username = message.from_user.username or message.from_user.full_name
    text = message.text or "<нет текста>"
    logging.info(f"Сообщение от {username}: {text}")

    # Сохраняем в Google Sheets
    sheet.append_row([username, text])

async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
