@@ -1,165 +1,168 @@
import logging
import json
from datetime import datetime, timedelta
import re
import os
import base64
import asyncio

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import os
import asyncio
from aiogram import Bot, Dispatcher, types

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# --- Google Sheets ---
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
creds_dict = json.loads(GOOGLE_CREDS_JSON)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Основной лист и Utro
main_sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
try:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Время"])

# --- Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Gmail API ---
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
gmail_service = build('gmail', 'v1', credentials=credentials)

# --- PARSE FUNCTIONS ---
def parse_order_message(text):
    """Парсим сообщение 'Пора делать заказ!'"""
    try:
        logging.info(f"Парсим текст: {text}")
        match = re.search(
            r"Заказ #([\wА-Яа-яЁё\d\-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) (?:ожидает|был оприходован)",
            text
        )
        if match:
            order_number = match.group(1)
            supplier = match.group(2)
            date = match.group(3)
            obj = match.group(4)
            return order_number, supplier, date, obj
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None, None, None

# --- TELEGRAM HANDLER ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")
    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в Google Sheets (A,B)")

# --- CHECK NEW ORDERS ---
async def check_new_orders():
    while True:
        try:
            logging.info("Читаем sheet1...")
            all_rows = main_sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[1] if len(row) > 1 else ""
                if "Пора делать заказ!" in text:
                    order_number, supplier, date, obj = parse_order_message(text)
                    if all([order_number, supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", now])
                        logging.info(f"Записано в Utro: {order_number}, {supplier}, {date}, {obj}")
        except Exception as e:
            logging.error(f"Ошибка при обработке заказов: {e}")
        await asyncio.sleep(5)

# --- SEND ALERTS ---
async def send_alerts():
    while True:
        try:
            logging.info("Проверка Utro для отправки уведомлений...")
            all_rows = utro_sheet.get_all_values()
            if len(all_rows) <= 1:
                await asyncio.sleep(3600)
                continue
            header, *data = all_rows
            one_hour_ago = datetime.now() - timedelta(hours=1)
            new_orders = []
            for row in data:
                if len(row) >= 6:
                    try:
                        ts = datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S")
                        if ts >= one_hour_ago:
                            new_orders.append(row)
                    except Exception:
                        continue
            if new_orders:
                msg_lines = ["📦 Новые заказы за последний час:"]
                for order in new_orders:
                    msg_lines.append(f"{order[1]} | {order[2]} | {order[3]}")
                await bot.send_message(ALERT_CHANNEL_ID, "\n".join(msg_lines))
                logging.info(f"Отправлено уведомление: {len(new_orders)} заказов")
            else:
                logging.info("Новых заказов нет")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)

# --- CHECK GMAIL ---
async def check_gmail_orders():
    while True:
        try:
            logging.info("Проверяем Gmail на письма 'Заказ отправлен'...")
            results = gmail_service.users().messages().list(userId='me', q='subject:"Заказ отправлен" is:unread').execute()
            messages = results.get('messages', [])
            for msg in messages:
                msg_data = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = msg_data['payload']
                body = payload.get('body', {}).get('data')
                if body:
                    msg_str = base64.urlsafe_b64decode(body.encode('ASCII')).decode('utf-8')
                    match = re.search(r"Заказ #([\wА-Яа-яЁё\d\-]+)", msg_str)
                    if match:
                        order_number = match.group(1)
                        logging.info(f"Найден заказ в письме: {order_number}")
                        all_rows = utro_sheet.get_all_values()
                        for idx, row in enumerate(all_rows[1:], start=2):
                            if row[0] == order_number:
                                utro_sheet.update_cell(idx, 5, "Отправлен")
                                logging.info(f"Заказ {order_number} обновлен в Utro как 'Отправлен'")
                # Помечаем письмо как прочитанное
                gmail_service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
        except HttpError as error:
            logging.error(f"Gmail API error: {error}")
        except Exception as e:
            logging.error(f"Ошибка при проверке Gmail: {e}")
        await asyncio.sleep(10)

# --- MAIN ---
async def main():
    logging.info("Бот запущен: обработка заказов, чтение канала и Gmail")
    await asyncio.gather(
        check_new_orders(),
        send_alerts(),
        check_gmail_orders(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
