import os
import json
import asyncio
import gspread
import logging
from aiogram import Bot, Dispatcher, types
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

# --- Переменные окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # без @

# --- Google Sheets ---
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# --- Бот ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Обработчик сообщений из канала ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Проверяем канал
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return

    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text[:50]}...")

    try:
        sheet.append_row([username, text])
        logging.info("Сообщение записано в Google Sheets")
    except Exception as e:
        logging.error(f"Ошибка при записи в Google Sheets: {e}")

# --- Main ---
async def main():
    logging.info("Бот запущен для чтения канала")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
