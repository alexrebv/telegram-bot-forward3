# Telegram → Google Sheets Bot

## Настройка
1. Создайте бота через @BotFather и получите токен.
2. Создайте Google Таблицу и скопируйте её ID (из URL).
3. Создайте сервисный аккаунт в Google Cloud и скачайте credentials.json.
4. Дайте доступ client_email из credentials.json к таблице (Editor).
5. Не загружайте credentials.json в GitHub!

## Railway Variables
- BOT_TOKEN = токен вашего бота
- SPREADSHEET_ID = ID вашей таблицы
- GOOGLE_CREDENTIALS = содержимое credentials.json (вставить целиком)

После запуска все входящие сообщения бота будут сохраняться в Google Sheets.
