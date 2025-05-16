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

# Khởi tạo Telegram Application như một biến toàn cục
telegram_app = Application.builder().token(TOKEN).build()

# Đăng ký handlers
telegram_app.add_handler(CommandHandler("start", start_game))
telegram_app.add_handler(CommandHandler("join", join_game))
telegram_app.add_handler(CommandHandler("begin", begin_game))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))

# Route chính
@app.route('/')
def index():
    return "Bot is running!"

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Xử lý update
        json_data = request.get_json()
        update = Update.de_json(json_data, telegram_app.bot)
        
        # Tạo event loop mới cho mỗi request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))
        loop.close()
        
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"Lỗi webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# Các hàm xử lý game
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game()
    global in_game
    in_game = True
    await update.message.reply_text("🎮 Bắt đầu trò chơi!\n👉 /join để tham gia\n👉 /begin để khởi động")

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players
    user = update.effective_user
    if user.id not in players:
        players.append(user.id)
        await update.message.reply_text(f"✅ {user.first_name} đã tham gia (Tổng: {len(players)})")
    else:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_player_index, waiting_for_phrase
    if len(players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi.")
        return
    waiting_for_phrase = True
    user_id = players[current_player_index]
    chat = await context.bot.get_chat(user_id)
    mention = f"<a href='tg://user?id={user_id}'>{chat.first_name}</a>"
    await update.message.reply_text(f"✏️ {mention}, hãy nhập cụm từ đầu tiên để bắt đầu!", parse_mode="HTML")
    await start_turn_timer(context)

async def play_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (giữ nguyên logic từ code trước)

# Khởi chạy ứng dụng
async def initialize():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    logger.info("Bot đã được khởi tạo và webhook đã được thiết lập")

if __name__ == '__main__':
    # Khởi tạo bot và set webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize())
    
    # Chạy Flask app
    app.run(host='0.0.0.0', port=PORT)
