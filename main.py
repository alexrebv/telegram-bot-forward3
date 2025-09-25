import os
import json
import logging
import asyncio
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Environment ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Telegram канал для чтения сообщений
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Google Sheets ---
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# --- Обработчик сообщений из канала ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return  # игнорируем сообщения из других каналов
    text = message.text or ""
    try:
        sheet.append_row([message.chat.title or "Telegram", text])
        logging.info(f"Сообщение из канала записано в sheet1: {text[:50]}...")
    except Exception as e:
        logging.error(f"Ошибка при записи в Google Sheet: {e}")

# --- Main ---
async def main():
    logging.info("Бот запущен: чтение сообщений из канала и запись в Google Sheet")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
