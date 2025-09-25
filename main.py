import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import re
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # канал для чтения
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # канал для уведомлений
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Авторизация Google
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Основной лист
main_sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Лист Utro
try:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = gc.open_by_key(SPREADSHEET_ID).add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Обработка сообщений канала ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")
    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в sheet1 (A, B)")

# --- Парсер заказов ---
def parse_order_message(text):
    """Извлекаем номер заказа, поставщика, дату и объект"""
    try:
        match = re.search(
            r"Заказ #[\d\-]+ (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) (?:ожидает|был|выполнен)",
            text
        )
        if match:
            supplier = match.group(1)
            date = match.group(2)
            obj = match.group(3)
            logging.info(f"Распарсено: {supplier}, {date}, {obj}")
            return supplier, date, obj
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None, None

# --- Проверка новых заказов ---
async def check_new_orders():
    while True:
        try:
            all_rows = main_sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[1] if len(row) > 1 else ""
                checked = row[5] if len(row) > 5 else ""
                if "Пора делать заказ!" in text and checked != "#checked":
                    logging.info(f"Новая строка для обработки: {text}")
                    supplier, date, obj = parse_order_message(text)
                    if all([supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([None, supplier, date, obj, "Новый", "#checked", now])
                        main_sheet.update_cell(idx, 6, "#checked")
                        logging.info(f"Строка {idx} отмечена как #checked, запись добавлена в Utro")
                    else:
                        logging.warning(f"Не удалось распарсить строку: {text}")
        except Exception as e:
            logging.error(f"Ошибка при обработке заказов: {e}")
        await asyncio.sleep(10)  # проверка каждые 10 секунд

# --- Отправка уведомлений ---
async def send_alerts():
    while True:
        try:
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
                        except Exception:
                            continue
                if new_orders:
                    msg_lines = ["📦 Новые заказы за последний час:"]
                    for order in new_orders:
                        msg_lines.append(f"{order[1]} | {order[2]} | {order[3]}")
                    await bot.send_message(ALERT_CHANNEL_ID, "\n".join(msg_lines))
                    logging.info(f"Отправлено уведомление: {len(new_orders)} заказ(ов)")
                else:
                    logging.info("Новых заказов нет")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)  # раз в час

# --- Запуск ---
async def main():
    logging.info("Бот запущен: обработка заказов, чтение канала и уведомления")
    await asyncio.gather(dp.start_polling(), check_new_orders(), send_alerts())

if __name__ == "__main__":
    asyncio.run(main())
