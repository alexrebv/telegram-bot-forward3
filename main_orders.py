import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import gspread
from aiogram import Bot
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # канал для оповещений

# Telegram bot
bot = Bot(token=BOT_TOKEN)

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

main_sheet = gc.sheet1  # основной лист с приходящими сообщениями
try:
    utro_sheet = gc.worksheet("Utro")
except gspread.exceptions.WorksheetNotFound:
    utro_sheet = gc.add_worksheet(title="Utro", rows="1000", cols="10")
    # Добавляем заголовки
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус"])

# Список поставщиков для группировки уведомлений
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
    """
    Парсит сообщение 'Пора делать заказ!' и возвращает:
    (номер заказа, поставщик, дата, объект)
    """
    if not text.startswith("Пора делать заказ!"):
        return None
    try:
        # Пример: Заказ #20250-609-0358 Сити ООО (поставка 25-09-2025) в ресторане DP+GHD Ярославский-06
        order_part = text.split("Заказ ")[1]
        order_number = order_part.split(" ")[0]
        supplier = next((s for s in SUPPLIERS if s in order_part), "Неизвестный")
        date_part = order_part.split("(")[1].split(")")[0].replace("поставка", "").strip()
        obj = order_part.split("в ресторане")[1].strip()
        return order_number, supplier, date_part, obj
    except Exception as e:
        logging.warning(f"Не удалось распарсить сообщение: {text}, ошибка: {e}")
        return None

async def process_new_orders():
    rows = main_sheet.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        text = row[1] if len(row) > 1 else ""
        status = row[2] if len(row) > 2 else ""
        if "#checked" in status:
            continue  # уже обработано

        parsed = parse_order_message(text)
        if parsed:
            order_number, supplier, order_date, obj = parsed
            utro_sheet.append_row([order_number, supplier, order_date, obj, "Новый"])
            # Отмечаем строку как обработанную
            main_sheet.update_cell(idx, 3, "#checked")
            logging.info(f"Добавлен заказ {order_number} в Utro")

async def send_alerts():
    """
    Группировка по поставщикам и дате и отправка оповещений в Telegram канал
    """
    rows = utro_sheet.get_all_values()[1:]
    alerts = {}
    for row in rows:
        if len(row) < 5:
            continue
        supplier, date, obj, status = row[1], row[2], row[3], row[4]
        if status != "Принято":
            alerts.setdefault((supplier, date), []).append(obj)

    for (supplier, date), objects in alerts.items():
        message_text = f"Накладные не приняты\n{supplier}\n{date}\n" + "\n".join(objects)
        await bot.send_message(chat_id=ALERT_CHANNEL_ID, text=message_text)
        logging.info(f"Отправлено уведомление для {supplier} {date}")

async def main_loop():
    last_alert_time = datetime.now() - timedelta(hours=1)
    while True:
        await process_new_orders()
        # Отправка уведомлений каждый час
        if datetime.now() - last_alert_time >= timedelta(hours=1):
            await send_alerts()
            last_alert_time = datetime.now()
        await asyncio.sleep(10)  # проверка новых заказов каждые 10 секунд

if __name__ == "__main__":
    logging.info("Бот заказов запущен")
    asyncio.run(main_loop())
