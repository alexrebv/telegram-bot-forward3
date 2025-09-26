import os
import json
import asyncio
import gspread
import logging
from aiogram import Bot, Dispatcher, types
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # @имя_канала

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Google Sheets
creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Проверяем, что сообщение именно из нужного канала
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return

    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")

    sheet.append_row([username, text])
    logging.info("Сообщение записано в Google Sheets")

async def main():
    logging.info("Бот запущен для чтения канала")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
