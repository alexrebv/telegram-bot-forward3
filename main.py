import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
import re
import gspread
from aiogram import Bot, Dispatcher, types
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # канал, куда пишут сообщения
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # канал для оповещений

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)

main_sheet = spreadsheet.sheet1
try:
    utro_sheet = spreadsheet.worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = spreadsheet.add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def parse_new_order(text: str):
    """Парсинг 'Пора делать заказ!'"""
    order_match = re.search(
        r"Заказ #([\d\-]+) (.+?) \(поставка (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) ожидает",
        text,
    )
    if order_match:
        order_number, supplier, date, obj = order_match.groups()
        return order_number, supplier, date, obj
    return None, None, None, None


def parse_accept_order(text: str):
    """Парсинг 'Заказ принят!'"""
    order_match = re.search(
        r"Заказ #([\d\-]+) (.+?) \(поставка (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) был оприходован",
        text,
    )
    if order_match:
        order_number, supplier, date, obj = order_match.groups()
        return order_number, supplier, date, obj
    return None, None, None, None


async def check_new_orders():
    """Проверяем новые строки в sheet1"""
    while True:
        try:
            all_rows = main_sheet.get_all_values()
            logging.info(f"Проверка sheet1: {len(all_rows)} строк")

            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[1] if len(row) > 1 else ""
                checked = row[5] if len(row) > 5 else ""

                if checked == "#checked":
                    continue

                if "Пора делать заказ!" in text:
                    order_number, supplier, date, obj = parse_new_order(text)
                    if all([order_number, supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", "#checked", now])
                        logging.info(f"Добавлен заказ в Utro: {order_number}, {supplier}, {date}, {obj}")
                        main_sheet.update_cell(idx, 6, "#checked")

                elif "был оприходован" in text or "Заказ принят" in text:
                    order_number, supplier, date, obj = parse_accept_order(text)
                    if all([order_number, supplier, date, obj]):
                        all_utro = utro_sheet.get_all_values()
                        for u_idx, u_row in enumerate(all_utro[1:], start=2):
                            if u_row[0] == order_number and u_row[3] == obj:
                                utro_sheet.update_cell(u_idx, 5, "Принято")
                                logging.info(f"Обновлён статус заказа {order_number} ({obj}) → Принято")
                        main_sheet.update_cell(idx, 6, "#checked")
        except Exception as e:
            logging.error(f"Ошибка при обработке заказов: {e}")
        await asyncio.sleep(10)


async def send_alerts():
    """Оповещения раз в час"""
    while True:
        try:
            all_rows = utro_sheet.get_all_values()
            if len(all_rows) > 1:
                header, *data = all_rows
                today = datetime.now().strftime("%d-%m-%Y")
                alerts = [row for row in data if row[2] == today and row[4] != "Принято"]

                if alerts:
                    msg_lines = ["⚠️ Накладные не приняты:"]
                    for order in alerts:
                        msg_lines.append(f"{order[1]} | {order[2]} | {order[3]}")
                    msg_text = "\n".join(msg_lines)
                    await bot.send_message(ALERT_CHANNEL_ID, msg_text)
                    logging.info(f"Отправлено уведомление: {len(alerts)} заказ(ов)")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)


@dp.channel_post()
async def handle_channel_post(message: types.Message):
    """Сохраняем новые сообщения из канала в sheet1"""
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return

    username = message.chat.title or "<канал>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")

    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в Google Sheets")


async def main():
    logging.info("Бот запущен для обработки заказов")
    await asyncio.gather(dp.start_polling(bot), check_new_orders(), send_alerts())


if __name__ == "__main__":
    asyncio.run(main())
