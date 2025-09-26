import logging
import json
import os
import asyncio

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# --- Google Sheets ---
creds_dict = json.loads(GOOGLE_CREDS_JSON)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

main_sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- CHANNEL MESSAGE HANDLER ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Сохраняем только сообщения из указанного канала
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")
    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в Google Sheets (A,B)")

# --- MAIN ---
async def main():
    logging.info("Бот запущен: запись сообщений из канала в Google Sheets")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
