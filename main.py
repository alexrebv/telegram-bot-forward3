import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import re
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Environment ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")         # Telegram канал для чтения сообщений
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # Канал для уведомлений
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GMAIL_QUERY = 'subject:"Заказ отправлен"'

# --- Google Sheets ---
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
main_sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
try:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Gmail ---
def get_gmail_service():
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/gmail.readonly'])
    service = build('gmail', 'v1', credentials=creds)
    return service

# --- Функции ---
def parse_order_message(text):
    try:
        logging.info(f"Парсинг текста: {text}")
        order_match = re.search(
            r"Заказ #([\d\-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) ожидает",
            text
        )
        if order_match:
            order_number = order_match.group(1)
            supplier = order_match.group(2)
            date = order_match.group(3)
            obj = order_match.group(4)
            return order_number, supplier, date, obj
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None, None, None

async def check_new_orders():
    while True:
        try:
            logging.info("Читаем sheet1 для новых заказов...")
            all_rows = main_sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[1] if len(row) > 1 else ""
                checked = row[5] if len(row) > 5 else ""
                if "Пора делать заказ!" in text and checked != "#checked":
                    order_number, supplier, date, obj = parse_order_message(text)
                    if all([order_number, supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", "#checked", now])
                        main_sheet.update_cell(idx, 6, "#checked")
                        logging.info(f"Добавлен заказ в Utro и отмечен как #checked: {order_number}")
        except Exception as e:
            logging.error(f"Ошибка при обработке заказов: {e}")
        await asyncio.sleep(10)

async def send_alerts():
    while True:
        try:
            logging.info("Проверка Utro для отправки уведомлений...")
            all_rows = utro_sheet.get_all_values()
            if len(all_rows) > 1:
                header, *data = all_rows
                one_hour_ago = datetime.now() - timedelta(hours=1)
                new_orders = []
                for row in data:
                    if len(row) >= 7:
                        try:
                            ts = datetime.strptime(row[6], "%Y-%m-%d %H:%M:%S")
                            if ts >= one_hour_ago:
                                new_orders.append(row)
                        except:
                            continue
                if new_orders:
                    msg_lines = ["📦 Новые заказы за последний час:"]
                    for order in new_orders:
                        msg_lines.append(f"{order[1]} | {order[2]} | {order[3]}")
                    msg_text = "\n".join(msg_lines)
                    await bot.send_message(ALERT_CHANNEL_ID, msg_text)
                    logging.info(f"Отправлено уведомление в канал: {len(new_orders)} заказ(ов)")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)

@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    text = message.text or ""
    main_sheet.append_row([message.chat.title or "Telegram", text])
    logging.info(f"Сообщение из канала записано в sheet1: {text[:50]}...")

async def check_gmail():
    service = get_gmail_service()
    while True:
        try:
            results = service.users().messages().list(userId='me', q=GMAIL_QUERY).execute()
            messages = results.get('messages', [])
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_data['payload']
                body_data = payload.get('body', {}).get('data')
                if not body_data:
                    # иногда тело письма в parts
                    parts = payload.get('parts', [])
                    if parts:
                        body_data = parts[0]['body'].get('data')
                if body_data:
                    msg_str = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8')
                    existing_rows = [r[1] for r in main_sheet.get_all_values()]
                    if msg_str not in existing_rows:
                        main_sheet.append_row(["Gmail", msg_str])
                        logging.info(f"Добавлено письмо в sheet1: {msg_str[:50]}...")
        except HttpError as e:
            logging.error(f"Gmail API error: {e}")
        await asyncio.sleep(10)

# --- Main ---
async def main():
    logging.info("Бот запущен: обработка заказов, канал и Gmail")
    await asyncio.gather(
        dp.start_polling(),
        check_new_orders(),
        send_alerts(),
        check_gmail()
    )

if __name__ == "__main__":
    asyncio.run(main())
