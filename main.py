import os
import json
import asyncio
import logging
import re
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")       # @канал, из которого пишем в sheet1
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # @канал, куда шлём уведомления

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Открываем таблицу
sh = gc.open_by_key(SPREADSHEET_ID)
main_sheet = sh.sheet1
try:
    utro_sheet = sh.worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = sh.add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])


# ===== Парсинг сообщений =====
def parse_order_message(text: str):
    try:
        logging.info(f"Пробуем парсить текст: {text}")
        order_match = re.search(
            r"Заказ #([\d\-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) ожидает",
            text,
        )
        if order_match:
            order_number = order_match.group(1)
            supplier = order_match.group(2)
            date = order_match.group(3)
            obj = order_match.group(4).strip()
            logging.info(f"✅ Успешно распарсили: {order_number}, {supplier}, {date}, {obj}")
            return order_number, supplier, date, obj
        else:
            logging.warning("⚠️ Регулярка не сработала!")
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None, None, None


# ===== Обработка сообщений из канала в sheet1 =====
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return

    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")

    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в sheet1")


# ===== Проверка новых заказов в sheet1 =====
async def check_new_orders():
    while True:
        try:
            logging.info("Читаем sheet1...")
            all_rows = main_sheet.get_all_values()
            logging.info(f"Найдено {len(all_rows)} строк в sheet1")

            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[1] if len(row) > 1 else ""
                checked = row[5] if len(row) > 5 else ""

                if "Пора делать заказ!" in text and checked != "#checked":
                    logging.info(f"Найдена новая строка: {text}")
                    order_number, supplier, date, obj = parse_order_message(text)
                    if all([order_number, supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", "#checked", now])
                        logging.info(f"✍ Записано в Utro: {order_number}, {supplier}, {date}, {obj}")
                        main_sheet.update_cell(idx, 6, "#checked")
                        logging.info(f"Строка {idx} в sheet1 отмечена как #checked")
                    else:
                        logging.warning(f"Не удалось распарсить строку: {text}")
        except Exception as e:
            logging.error(f"Ошибка при проверке заказов: {e}")
        await asyncio.sleep(10)


# ===== Отправка уведомлений =====
async def send_alerts():
    while True:
        try:
            logging.info("Проверяем Utro для уведомлений...")
            all_rows = utro_sheet.get_all_values()
            logging.info(f"В Utro {len(all_rows)} строк")

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
                    msg_text = "\n".join(msg_lines)
                    await bot.send_message(ALERT_CHANNEL_ID, msg_text)
                    logging.info(f"✅ Уведомление отправлено в {ALERT_CHANNEL_ID} ({len(new_orders)} заказов)")
                else:
                    logging.info("Новых заказов за последний час нет")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)


# ===== Запуск =====
async def main():
    logging.info("Бот запущен для чтения канала и обработки заказов")
    await asyncio.gather(
        dp.start_polling(bot),
        check_new_orders(),
        send_alerts(),
    )


if __name__ == "__main__":
    asyncio.run(main())
