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

# Google credentials
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

@dp.message()
async def save_channel_message(message: Message):
    # В канале from_user обычно None, автор канала в sender_chat
    author = message.sender_chat.title if message.sender_chat else "Unknown"
    text = message.text or "<нет текста>"
    
    # Сохраняем в Google Sheets
    sheet.append_row([author, text])
    logging.info(f"Сохранено сообщение от {author}: {text}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
