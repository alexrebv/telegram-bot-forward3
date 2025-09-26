import os
import json
import asyncio
import gspread
import logging
from aiogram import Bot, Dispatcher, types
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

# ---------------- Конфигурация ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# ---------------- Google Sheets ----------------
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Добавим заголовки, если лист пустой
if sheet.row_count == 0 or sheet.get_all_values() == []:
    sheet.append_row(["Message ID", "Username", "Text", "Date"])

# ---------------- Aiogram ----------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- Обработчик сообщений ----------------
@dp.message()
async def save_message(message: types.Message):
    message_id = message.message_id
    user = message.from_user.username or message.from_user.full_name
    text = message.text or "<нет текста>"
    date = message.date.strftime("%Y-%m-%d %H:%M:%S")

    # Получаем уже записанные message_id
    existing_ids = sheet.col_values(1)
    if str(message_id) in existing_ids:
        logging.info(f"Пропущено (дубликат): {message_id}")
        return

    # Сохраняем сообщение в Google Sheets
    sheet.append_row([message_id, user, text, date])
    logging.info(f"Новое сообщение сохранено: {message_id} | {text}")

    # Ответ пользователю (можно закомментировать)
    await message.answer("✅ Сообщение сохранено в Google Sheets")

# ---------------- Главная функция ----------------
async def main():
    logging.info("Бот запущен, ожидаем новые сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
