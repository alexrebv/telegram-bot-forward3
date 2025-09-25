import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Environment & Config ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # без @
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = "sheet1"
BATCH_SIZE = 100      # сообщений в одной пачке
WAIT_MS = 5000        # таймаут в миллисекундах

# --- Google Sheets ---
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Gmail Service ---
def get_gmail_service():
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/gmail.readonly'])
    service = build('gmail', 'v1', credentials=creds)
    return service

# --- Обработка сообщений из канала ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID:
        return
    text = message.text or ""
    try:
        sheet.append_row([message.chat.title or "Telegram", text])
        logging.info(f"Сообщение из канала записано в {SHEET_NAME}: {text[:50]}...")
    except Exception as e:
        logging.error(f"Ошибка записи в таблицу: {e}")

# --- Проверка Gmail ---
async def check_gmail():
    service = get_gmail_service()
    while True:
        try:
            results = service.users().messages().list(userId='me', q='subject:"Заказ отправлен"', maxResults=BATCH_SIZE).execute()
            messages = results.get('messages', [])
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_data['payload']
                body_data = payload.get('body', {}).get('data')
                if not body_data:
                    parts = payload.get('parts', [])
                    if parts:
                        body_data = parts[0]['body'].get('data')
                if body_data:
                    msg_str = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8')
                    existing_rows = [r[1] for r in sheet.get_all_values()]
                    if msg_str not in existing_rows:
                        sheet.append_row(["Gmail", msg_str])
                        logging.info(f"Добавлено письмо в {SHEET_NAME}: {msg_str[:50]}...")
                        await asyncio.sleep(WAIT_MS / 1000)
        except HttpError as e:
            logging.error(f"Gmail API error: {e}")
        except Exception as e:
            logging.error(f"Ошибка обработки Gmail: {e}")
        await asyncio.sleep(10)

# --- Main ---
async def main():
    logging.info("Бот запущен: чтение канала и Gmail")
    await asyncio.gather(
        dp.start_polling(bot),
        check_gmail()
    )

if __name__ == "__main__":
    asyncio.run(main())
