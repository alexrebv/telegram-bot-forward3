import os
import json
import asyncio
import logging
import re
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types
import imaplib
import email

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # канал для чтения сообщений
ALERT_CHANNEL_ID = os.getenv("ALERT_CHANNEL_ID")  # канал для оповещений
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Gmail
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
IMAP_SERVER = "imap.gmail.com"

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

main_sheet = gc.sheet1
try:
    utro_sheet = gc.worksheet("Utro")
except gspread.WorksheetNotFound:
    utro_sheet = gc.add_worksheet(title="Utro", rows="100", cols="10")
    utro_sheet.append_row(["Номер заказа", "Поставщик", "Дата", "Объект", "Статус", "Checked", "Время"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- Telegram -----------------
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")
    main_sheet.append_row([text, "", "", "", "", "", ""])  # записываем только A и B
    logging.info("Сообщение записано в sheet1")

# ---------------- Парсинг -----------------
def parse_order_message(text):
    """Парсим 'Пора делать заказ!'"""
    try:
        match = re.search(
            r"Заказ #([\d\-]+) (.+?) \((?:поставка|доставка) (\d{2}-\d{2}-\d{4})\) в ресторане (.+?) ",
            text
        )
        if match:
            order_number = match.group(1)
            supplier = match.group(2)
            date = match.group(3)
            obj = match.group(4)
            logging.info(f"Парсинг успешен: {order_number}, {supplier}, {date}, {obj}")
            return order_number, supplier, date, obj
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None, None, None

async def check_new_orders():
    """Проверка новых заказов в sheet1 каждые 10 секунд"""
    while True:
        try:
            all_rows = main_sheet.get_all_values()
            logging.info(f"Всего строк в sheet1: {len(all_rows)}")
            for idx, row in enumerate(all_rows[1:], start=2):
                text = row[0] if len(row) > 0 else ""
                checked = row[5] if len(row) > 5 else ""
                if "Пора делать заказ!" in text and checked != "#checked":
                    order_number, supplier, date, obj = parse_order_message(text)
                    if all([order_number, supplier, date, obj]):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        utro_sheet.append_row([order_number, supplier, date, obj, "Новый", "#checked", now])
                        main_sheet.update_cell(idx, 6, "#checked")
                        logging.info(f"Добавлен заказ {order_number} в Utro")
        except Exception as e:
            logging.error(f"Ошибка при обработке заказов: {e}")
        await asyncio.sleep(10)

# ---------------- Gmail -----------------
def fetch_new_gmail_messages():
    """Возвращает список новых писем, где заказ отправлен"""
    messages = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("inbox")
        status, data = mail.search(None, '(UNSEEN SUBJECT "Заказ для ресторана")')
        if status != "OK":
            return messages
        for num in data[0].split():
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        messages.append(part.get_payload(decode=True).decode())
            else:
                messages.append(msg.get_payload(decode=True).decode())
            # отмечаем письмо как прочитанное
            mail.store(num, '+FLAGS', '\\Seen')
        mail.logout()
    except Exception as e:
        logging.error(f"Ошибка Gmail: {e}")
    return messages

async def process_gmail_orders():
    """Обработка сообщений Gmail каждые 30 секунд"""
    while True:
        try:
            messages = fetch_new_gmail_messages()
            for text in messages:
                match = re.search(
                    r"Заказ для ресторана (.+?) #([\d\-]+) создан",
                    text
                )
                if match:
                    obj = match.group(1)
                    order_number = match.group(2)
                    all_rows = utro_sheet.get_all_values()
                    for idx, row in enumerate(all_rows[1:], start=2):
                        if len(row) >= 4 and row[0] == order_number and row[3] == obj:
                            utro_sheet.update_cell(idx, 5, "Заказ оформлен")
                            logging.info(f"Обновлен заказ {order_number} для объекта {obj}")
        except Exception as e:
            logging.error(f"Ошибка при обработке Gmail заказов: {e}")
        await asyncio.sleep(30)

# ---------------- Оповещения -----------------
async def send_alerts():
    """Отправка новых заказов раз в час"""
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
                    logging.info(f"Отправлено уведомление в канал: {len(new_orders)} заказ(ов)")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомлений: {e}")
        await asyncio.sleep(3600)

# ---------------- Main -----------------
async def main():
    logging.info("Бот запущен")
    await asyncio.gather(
        dp.start_polling(bot),
        check_new_orders(),
        process_gmail_orders(),
        send_alerts()
    )

if __name__ == "__main__":
    asyncio.run(main())
