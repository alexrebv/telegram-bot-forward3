import os
import json
import asyncio
import gspread
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # @SuppliersODaccept

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID)
utro_sheet = sheet.worksheet("Utro")

# Поставщики
SUPPLIERS = [
    "ООО \"ТД Восток\" (без кофе)",
    "ООО Фабрика ВБ",
    "ИП Сенникова А.А.",
    "ИП Есаулкова В.Г.",
    "ООО «МЕГАФУД»",
    "Сити ООО",
    "ИП Макеев Артем Юрьевич(гр.1,2,нов)",
    "ИП Хондкарян А. С.",
    "ООО \"Минводы Боржоми\"",
    "ООО ТД Лето",
    "Скай ООО (RedBull)",
    "МОЛОЧНАЯ ИМПЕРИЯ ООО",
    "ООО МясПродукт"
]

CHECKED_COLUMN = 5  # столбец для отметки, что строка уже обработана

def parse_order_message(text):
    """
    Парсит сообщение вида:
    Пора делать заказ!
    Заказ #20250-609-0358 Сити ООО (поставка 25-09-2025) в ресторане DP+GHD Ярославский-06 ожидает подтверждения
    """
    try:
        if "Пора делать заказ!" not in text:
            return None
        # Номер заказа
        order_idx = text.index("#") + 1
        order_end = text.index(" ", order_idx)
        order_number = text[order_idx:order_end]

        # Поставщик
        supplier = next((s for s in SUPPLIERS if s in text), None)

        # Дата
        date_start = text.index("(поставка") + len("(поставка ")
        date_end = text.index(")", date_start)
        order_date = text[date_start:date_end]

        # Объект
        obj_start = text.index("в ресторане") + len("в ресторане ")
        obj_end = text.index(" ожидает", obj_start)
        obj = text[obj_start:obj_end]

        return order_number, supplier, order_date, obj
    except Exception as e:
        logging.warning(f"Не удалось распарсить сообщение: {text}, ошибка: {e}")
        return None

async def process_new_orders():
    while True:
        try:
            rows = utro_sheet.get_all_values()
            for idx, row in enumerate(rows[1:], start=2):  # пропускаем заголовки
                checked = row[CHECKED_COLUMN - 1] if len(row) >= CHECKED_COLUMN else ""
                if checked == "#checked":
                    continue

                text = row[1] if len(row) > 1 else ""
                parsed = parse_order_message(text)
                if parsed:
                    order_number, supplier, order_date, obj = parsed
                    # Обновляем строку в листе Utro
                    utro_sheet.update(f"A{idx}:D{idx}", [[order_number, supplier, order_date, obj]])
                    utro_sheet.update_cell(idx, CHECKED_COLUMN, "#checked")
                    logging.info(f"Обработан заказ {order_number} для {obj}")
        except Exception as e:
            logging.error(f"Ошибка при обработке новых заказов: {e}")

        await asyncio.sleep(10)  # проверка каждые 10 секунд

async def send_delivery_alerts():
    while True:
        try:
            rows = utro_sheet.get_all_values()
            alerts = {}
            for row in rows[1:]:
                order_number = row[0] if len(row) > 0 else None
                supplier = row[1] if len(row) > 1 else None
                order_date = row[2] if len(row) > 2 else None
                obj = row[3] if len(row) > 3 else None
                status = row[4] if len(row) > 4 else ""

                if order_number and supplier and order_date and obj and status != "#checked":
                    # Если доставка ожидается, добавляем в словарь по поставщику и дате
                    key = (supplier, order_date)
                    if key not in alerts:
                        alerts[key] = []
                    alerts[key].append(obj)

            for (supplier, date), objs in alerts.items():
                message = f"Накладные не приняты\n{supplier}\n{date}\n" + "\n".join(objs)
                await bot.send_message(chat_id=ALERT_CHANNEL_ID, text=message)
                logging.info(f"Отправлено оповещение для {supplier}, {date}")
        except Exception as e:
            logging.error(f"Ошибка при отправке оповещений: {e}")

        await asyncio.sleep(3600)  # раз в час

async def main():
    logging.info("Бот заказов запущен")
    await asyncio.gather(
        process_new_orders(),
        send_delivery_alerts()
    )

if __name__ == "__main__":
    asyncio.run(main())
