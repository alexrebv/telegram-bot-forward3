bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- HELPER FUNCTIONS ---
def get_existing_message_ids():
    """Возвращает множество ID сообщений, которые уже есть в sheet1"""
    all_values = main_sheet.get_all_values()
    return set(row[0] for row in all_values[1:] if len(row) > 0)

async def fetch_and_sync_channel():
    """Синхронизирует канал с листом, добавляя недостающие сообщения"""
    existing_ids = get_existing_message_ids()
    chat = await bot.get_chat(CHANNEL_ID)
    last_message_id = None
    more = True

    while more:
        history = await bot.get_chat_history(chat.id, limit=100, offset_id=last_message_id or 0)
        if not history:
            break
        for msg in history:
            msg_id = str(msg.message_id)
            if msg_id not in existing_ids:
                text = msg.text or "<нет текста>"
                username = msg.chat.title or "<название канала>"
                main_sheet.append_row([msg_id, username, text])
                logging.info(f"Добавлено сообщение {msg_id}: {text}")
        last_message_id = history[-1].message_id
        more = len(history) == 100  # если меньше 100 — дошли до конца

# --- CHANNEL MESSAGE HANDLER ---
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Сохраняем только сообщения из указанного канала
    if message.chat.username != CHANNEL_ID.replace("@", ""):
        return
    msg_id = str(message.message_id)
    existing_ids = get_existing_message_ids()
    if msg_id in existing_ids:
        return  # уже есть
    username = message.chat.title or "<название канала>"
    text = message.text or "<нет текста>"
    logging.info(f"Получено сообщение из канала: {text}")
    main_sheet.append_row([username, text])
    logging.info("Сообщение записано в Google Sheets (A,B)")
    main_sheet.append_row([msg_id, username, text])
    logging.info(f"Новое сообщение записано: {msg_id} | {text}")

# --- MAIN ---
async def main():
    logging.info("Бот запущен: запись сообщений из канала в Google Sheets")
    logging.info("Бот запущен: синхронизация канала с Google Sheets")
    # Первичная синхронизация
    await fetch_and_sync_channel()
    logging.info("Первая синхронизация завершена")
    # Постоянная обработка новых сообщений
    await dp.start_polling(bot)

if __name__ == "__main__":
