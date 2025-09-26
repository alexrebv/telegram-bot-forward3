import os
import json
import asyncio
import logging
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # без @
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# --- Google Sheets ---
creds_dict = json.loads(GOOGLE_CREDS_JSON)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1  # лист sheet1

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Обработчик сообщений из канала ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Проверяем, что сообщение именно из нужного канала
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return

    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text[:50]}...")

    try:
        # Записываем в Google Sheets
        sheet.append_row([username, text])
        logging.info("Сообщение записано в Google Sheets (A,B)")
    except Exception as e:
        logging.error(f"Ошибка при записи в Google Sheets: {e}")

# --- Main ---
async def main():
    logging.info("Бот запущен для чтения канала")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
