import os
import json
import asyncio
import gspread
import logging
import re
from datetime import datetime
from aiogram import Bot
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # "@SuppliersODaccept"

bot = Bot(token=BOT_TOKEN)

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID)
utro_sheet = sheet.worksheet("Utro")

# Список поставщиков
SUPPLIERS = [
    'ООО "ТД Восток" (без кофе)', 'ООО Фабрика ВБ', 'ИП Сенникова А.А.',
    'ИП Есаулкова В.Г.', 'ООО «МЕГАФУД»', 'Сити ООО',
    'ИП Макеев Артем Юрьевич(гр.1,2,нов)', 'ИП Хондкарян А. С.',
    'ООО "Минводы Боржоми"', 'ООО ТД Лето', 'Скай ООО (RedBull)',
    'МОЛОЧНАЯ ИМПЕРИЯ ООО', 'ООО МясПродукт'
]

# Регулярки для разбора сообщений
ORDER_REGEX = re.compile(r"Заказ\s+#(\S+)\s+(.+?)\s+\(поставка\s+(\d{2}-\d{2}-\d{4})\)\s+в\s+ресторане\s+(.+?)\s+ожидает подтверждения")
SENT_REGEX = re.compile(r"Заказ для ресторана\s+(.+?)\s+#(\S+)\s+создан")
DELIVERY_REGEX = re.compile(r"Ожидается доставка!\s+Заказ\s+#(\S+)\s+(.+?)\s+\(доставка\s+(\d{2}-\d{2}-\d{4})\)")

async def process_orders():
    while True:
        try:
            # Читаем все строки с Utro
            rows = utro_sheet.get_all_values()
            for i, row in enumerate(rows):
                if len(row) < 5:
                    continue
                order_number = row[0]
                supplier = row[1]
                date = row[2]
                obj = row[3]
                status = row[4]

                # Если заказ не отправлен, ищем письмо в Google Sheet (имитация)
                # Тут можно подключить чтение почты через Gmail API и искать по SUBJECT/SENT_REGEX

                # Пример оповещения по доставке
                # Если строка соответствует DELIVERY_REGEX и статус не "Накладная принята"
                # Тут для примера просто оповещаем каждые строки
                if status != "Накладная принята":
                    text = f"Накладные не приняты\n{supplier}\n{date}\n{obj}"
                    await bot.send_message(chat_id=ALERT_CHANNEL_ID, text=text)

        except Exception as e:
            logging.error(f"Ошибка обработки заказов: {e}")

        await asyncio.sleep(3600)  # проверка каждый час

async def main():
    logging.info("Бот запущен для обработки заказов")
    await process_orders()

if __name__ == "__main__":
    asyncio.run(main())
