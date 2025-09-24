import os
import json
import logging
import gspread
import base64
import re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from aiogram import Bot

logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = "@SuppliersODaccept"
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# Настройка бота
bot = Bot(token=BOT_TOKEN)

# Настройка Google Sheets
creds_dict = json.loads(GOOGLE_CREDENTIALS)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/gmail.readonly"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID)
utro_sheet = sheet.worksheet("Utro")  # Лист для новых заказов
main_sheet = sheet.sheet1  # Основной лист с приходящими сообщениями

# Настройка Gmail API
gmail_service = build("gmail", "v1", credentials=credentials)

# Список поставщиков
SUPPLIERS = [
    'ООО "ТД Восток" (без кофе)',
    'ООО Фабрика ВБ',
    'ИП Сенникова А.А.',
    'ИП Есаулкова В.Г.',
    'ООО «МЕГАФУД»',
    'Сити ООО',
    'ИП Макеев Артем Юрьевич(гр.1,2,нов)',
    'ИП Хондкарян А. С.',
    'ООО "Минводы Боржоми"',
    'ООО ТД Лето',
    'Скай ООО (RedBull)',
    'МОЛОЧНАЯ ИМПЕРИЯ ООО',
    'ООО МясПродукт'
]

def parse_order_message(text):
    """Парсим строку типа 'Пора делать заказ!'"""
    pattern = r"Заказ #([\d-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) "
    match = re.search(pattern, text)
    if match:
        order_number, supplier, date, obj = match.groups()
        return order_number, supplier, date, obj
    return None, None, None, None

def parse_email_subject(subject):
    """Парсим тему письма из Gmail"""
    pattern = r"Заказ для ресторана (.+?) #([\d-]+) создан"
    match = re.search(pattern, subject)
    if match:
        obj, order_number = match.groups()
        return order_number, obj
    return None, None

def get_new_gmail_messages():
    """Получаем новые письма Gmail"""
    results = gmail_service.users().messages().list(userId='me', q="is:unread").execute()
    messages = results.get('messages', [])
    parsed_messages = []
    for msg in messages:
        msg_data = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        order_number, obj = parse_email_subject(subject)
        if order_number and obj:
            parsed_messages.append((order_number, obj))
    return parsed_messages

def process_utro_sheet():
    """Обрабатываем новые сообщения 'Пора делать заказ!'"""
    rows = main_sheet.get_all_values()
    for row in rows:
        text = row[1] if len(row) > 1 else ""
        if "Пора делать заказ!" in text:
            order_number, supplier, date, obj = parse_order_message(text)
            if order_number and supplier and date and obj:
                utro_sheet.append_row([order_number, supplier, date, obj])
                logging.info(f"Добавлен заказ {order_number} в лист Utro")

def update_orders_from_gmail():
    """Отмечаем заказы как оформленные на основе Gmail"""
    messages = get_new_gmail_messages()
    if not messages:
        return
    utro_rows = utro_sheet.get_all_values()
    for order_number, obj in messages:
        for idx, row in enumerate(utro_rows, start=1):
            if len(row) < 4:
                continue
            if row[0] == order_number and row[3] == obj:
                # Обновляем статус в столбце "Заказ" (5-й столбец)
                utro_sheet.update_cell(idx, 5, "Оформлен")
                logging.info(f"Заказ {order_number} оформлен для {obj}")

def send_unreceived_notifications():
    """Отправляем уведомления по заказам, которые ожидают доставку"""
    utro_rows = utro_sheet.get_all_values()
    grouped = {}
    for row in utro_rows:
        if len(row) < 5:
            continue
        order_number, supplier, date, obj, status = row[:5]
        if status != "Оформлен":
            key = (supplier, date)
            grouped.setdefault(key, []).append(obj)

    for (supplier, date), objects in grouped.items():
        message = f"Накладные не приняты\n{supplier}\n{date}\n" + "\n".join(objects)
        bot.send_message(chat_id=CHANNEL_ID, text=message)
        logging.info(f"Отправлено уведомление по {supplier} на {date}")

def main():
    logging.info("Запуск обработки заказов")
    process_utro_sheet()
    update_orders_from_gmail()
    send_unreceived_notifications()
    logging.info("Обработка завершена")

if __name__ == "__main__":
    main()
