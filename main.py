import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Cấu hình
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Khởi tạo Flask app
app = Flask(__name__)

# Khởi tạo Telegram Application
def init_telegram_app():
    application = Application.builder().token(TOKEN).build()
    
    # Đăng ký handlers
    application.add_handler(CommandHandler("start", start_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("begin", begin_game))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))
    
    return application

# Biến toàn cục cho Telegram Application
telegram_app = None

# Route chính
@app.route('/')
def index():
    return "Bot is running!"

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    global telegram_app
    try:
        # Khởi tạo nếu chưa có
        if telegram_app is None:
            telegram_app = init_telegram_app()
            asyncio.run(telegram_app.initialize())
        
        # Xử lý update
        json_data = request.get_json()
        update = Update.de_json(json_data, telegram_app.bot)
        
        # Sử dụng event loop riêng để xử lý async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))
        loop.close()
        
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"Lỗi webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Các hàm xử lý game (giữ nguyên từ code của bạn)
    async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (giữ nguyên)

    async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (giữ nguyên)

    async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (giữ nguyên)

    async def play_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (giữ nguyên)

# Khởi chạy ứng dụng
if __name__ == '__main__':
    # Khởi tạo và set webhook
    async def main():
        global telegram_app
        telegram_app = init_telegram_app()
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
    
    # Chạy Flask app
    app.run(host='0.0.0.0', port=PORT)
