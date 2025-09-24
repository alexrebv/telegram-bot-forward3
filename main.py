import os
import json
import asyncio
import logging
import re
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# -----------------------------
# Переменные окружения
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")        # Канал для чтения сообщений
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # Канал для уведомлений
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GMAIL_USER = os.getenv("GMAIL_USER")        # Почта для Gmail API

# -----------------------------
# Google Sheets
# -----------------------------
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
SCOPES_SHEETS = ["https://www.googleapis.com/auth/spreadsheets"]
credentials_sheets = Credentials.from_service_account_info(creds_dict, scopes=SCOPES_SHEETS)
gc = gspread.authorize(credentials_sheets)

main_sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
try:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])

# -----------------------------
# Gmail API
# -----------------------------
SCOPES_GMAIL = ['https://www.googleapis.com/auth/gmail.readonly']
credentials_gmail = Credentials.from_service_account_info(creds_dict, scopes=SCOPES_GMAIL).with_subject(GMAIL_USER)
gmail_service = build('gmail', 'v1', credentials=credentials_gmail)

# -----------------------------
# Telegram Bot
# -----------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -----------------------------
# Функции
# -----------------------------
def parse_order_message(text):
    """Парсим сообщение 'Пора делать заказ!'"""
    order_match = re.search(
        r"Заказ #([\d\-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) ",
        text
    )
    if order_match:
        return order_match.group(1), order_match.group(2), order_match.group(3), order_match.group(4)
    return None, None, None, None

def get_new_orders_from_gmail():
    """Получаем новые письма с Gmail и парсим заказы"""
    try:
        results = gmail_service.users().messages().list(
            userId='me', labelIds=['INBOX'], q='is:unread'
        ).execute()
        messages = results.get('messages', [])
        orders = []

        for msg in messages:
            msg_data = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
            subject = ''
            for header in msg_data['payload']['headers']:
                if header['name'] == 'Subject':
                    subject = header['value']

            if 'Пора делать заказ!' in subject:
                order_number, supplier, date, obj = parse_order_message(subject)
                if all([order_number, supplier, date, obj]):
                    orders.append((order_number, supplier, date, obj))

            # Помечаем письмо как прочитанное
            gmail_service.users().messages().modify(
                userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}
            ).execute()
        return orders
    except HttpError as e:
        logging.error(f"Gmail API error: {e}")
        return []

def add_orders_to_utro(orders):
    """Добавляем заказы в Utro, проверяя #checked"""
    from datetime import datetime
    for order_number, supplier, date, obj in orders:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", "#checked", now])
        logging.info(f"Добавлено в Utro: {order_number}, {supplier}, {date}, {obj}")

# -----------------------------
# Telegram хэндлер
# -----------------------------
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    text = message.text or ""
    username = message.chat.title or "<канал>"
    main_sheet.append_row([username, text])
    logging.info(f"Сообщение из канала записано в sheet1: {text}")

# -----------------------------
# Проверка новых заказов из sheet1
# -----------------------------
async def check_new_orders():
    while True:
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
                    logging.info(f"Обработан заказ из sheet1: {order_number}, {supplier}, {date}, {obj}")
        await asyncio.sleep(10)

# -----------------------------
# Проверка Gmail каждые 10 секунд
# -----------------------------
async def check_gmail_loop():
    while True:
        orders = get_new_orders_from_gmail()
        if orders:
            add_orders_to_utro(orders)
        await asyncio.sleep(10)

# -----------------------------
# Отправка уведомлений из Utro раз в час
# -----------------------------
async def send_alerts():
    while True:
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
                await bot.send_message(ALERT_CHANNEL_ID, "\n".join(msg_lines))
                logging.info(f"Отправлено уведомление: {len(new_orders)} заказ(ов)")
        await asyncio.sleep(3600)

# -----------------------------
# Главная функция
# -----------------------------
async def main():
    logging.info("Бот запущен: обработка заказов, чтение канала и Gmail")
    await asyncio.gather(
        dp.start_polling(),
        check_new_orders(),
        check_gmail_loop(),
        send_alerts()
    )

if __name__ == "__main__":
    asyncio.run(main())
