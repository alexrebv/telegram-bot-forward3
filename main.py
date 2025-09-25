import os
import json
import asyncio
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

# -------------------------------
# Настройки
# -------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # без @
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = "sheet1"

# Ограничение логов, чтобы не перегружать Railway
logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(message)s')

# -------------------------------
# Google Sheets
# -------------------------------
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# -------------------------------
# Telegram Bot
# -------------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------------------
# Обработчик сообщений канала
# -------------------------------
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Проверка канала
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    if not message.text:
        return  # пропускаем медиа и др. типы
    if "Заказ отправлен" not in message.text:
        return  # фильтр по ключевой фразе

    try:
        # Добавляем сообщение в Google Sheets
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([message.chat.title or "Telegram", message.text, now])
        logging.error(f"Сообщение добавлено в лист: {message.text[:50]}...")
    except Exception as e:
        logging.error(f"Ошибка добавления в Google Sheets: {e}")

# -------------------------------
# Основной цикл
# -------------------------------
async def main():
    print("Бот запущен для чтения сообщений канала...")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
