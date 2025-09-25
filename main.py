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
BATCH_SIZE = 100      # сообщений в одной пачке
WAIT_MS = 5000        # таймаут в миллисекундах

# Ограничение логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# -------------------------------
# Google Sheets
# -------------------------------
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# Получаем уже существующие сообщения для проверки дубликатов
existing_texts = set(r[1] for r in sheet.get_all_values()[1:])  # пропускаем заголовок

# -------------------------------
# Telegram Bot
# -------------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()  # без передачи bot

# -------------------------------
# Обработчик сообщений канала
# -------------------------------
processed_count = 0

@dp.channel_post()
async def handle_channel_post(message: types.Message):
    global processed_count
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    text = message.text or ""
    if not text or "Заказ отправлен" not in text:
        return
    if text in existing_texts:
        logging.info("Дубликат пропущен")
        return

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([message.chat.title or "Telegram", text, now])
        existing_texts.add(text)
        processed_count += 1
        logging.info(f"Добавлено сообщение: {text[:50]}...")

        # Таймаут каждые BATCH_SIZE сообщений
        if processed_count % BATCH_SIZE == 0:
            logging.info(f"Обработано {processed_count} сообщений, делаем паузу {WAIT_MS/1000} сек...")
            await asyncio.sleep(WAIT_MS / 1000)

    except Exception as e:
        logging.error(f"Ошибка при добавлении в Google Sheets: {e}")

# -------------------------------
# Основной цикл
# -------------------------------
async def main():
    print("Бот запущен для чтения сообщений канала...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
