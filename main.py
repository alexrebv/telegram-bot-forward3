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
CHANNEL_ID = os.getenv("CHANNEL_ID")  # @имя_канала
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

# --- Helper function ---
def get_existing_message_ids():
    """Возвращает множество ID сообщений, которые уже есть в sheet1"""
    all_values = main_sheet.get_all_values()
    return set(row[0] for row in all_values[1:] if len(row) > 0)

# --- CHANNEL MESSAGE HANDLER ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    """Сохраняет новые сообщения из канала в Google Sheets"""
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    msg_id = str(message.message_id)
    existing_ids = get_existing_message_ids()
    if msg_id in existing_ids:
        return  # уже есть
    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    main_sheet.append_row([msg_id, username, text])
    logging.info(f"Новое сообщение записано: {msg_id} | {text}")

# --- MAIN ---
async def main():
    logging.info("Бот запущен: запись новых сообщений из канала в Google Sheets")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
