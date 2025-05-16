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

# ========== KHAI BÁO BIẾN TOÀN CỤC ==========
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Biến trạng thái game
players = []
current_phrase = ""
used_phrases = set()
current_player_index = 0
in_game = False
waiting_for_phrase = False
turn_timeout_task = None
win_counts = {}

BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}

# ========== ĐỊNH NGHĨA CÁC HÀM PHỤ TRỢ ==========
def reset_game():
    global players, current_phrase, used_phrases, current_player_index, in_game, waiting_for_phrase, turn_timeout_task
    players = []
    current_phrase = ""
    used_phrases = set()
    current_player_index = 0
    in_game = False
    waiting_for_phrase = False
    if turn_timeout_task:
        turn_timeout_task.cancel()
        turn_timeout_task = None

def is_vietnamese(text):
    vietnamese_chars = r'[àáạảãâầấậẩẫăắặẳẵêèéẹẻẽềếệểễìíịỉĩòóọỏõôồốộổỗơớợởỡùúụủũưứựửữỳýỵỷỹđ]'
    return bool(re.search(vietnamese_chars, text.lower()))

def contains_bad_word(phrase):
    return any(bad_word in phrase.lower().split() for bad_word in BAD_WORDS)

# ========== ĐỊNH NGHĨA CÁC HANDLERS ==========
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game()
    global in_game
    in_game = True
    await update.message.reply_text(
        "🎮 Bắt đầu trò chơi!\n"
        "👉 /join để tham gia\n"
        "👉 /begin để khởi động"
    )

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
    user = await context.bot.get_chat(user_id)
    await update.message.reply_text(
        f"✏️ {user.first_name}, hãy nhập cụm từ đầu tiên để bắt đầu!",
        parse_mode="HTML"
    )

# ========== PHẦN CÒN LẠI CỦA CODE ==========
# ... (các hàm khác như play_word, eliminate_player, declare_winner, etc.)

# Khởi tạo Flask app
app = Flask(__name__)

# Khởi tạo Telegram Application
telegram_app = Application.builder().token(TOKEN).build()

# Đăng ký handlers
telegram_app.add_handler(CommandHandler("start", start_game))
telegram_app.add_handler(CommandHandler("join", join_game))
telegram_app.add_handler(CommandHandler("begin", begin_game))
# ... (đăng ký các handlers khác)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, telegram_app.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))
        loop.close()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Lỗi webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    # Khởi tạo bot
    async def initialize():
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
        logger.info("Bot đã sẵn sàng hoạt động")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize())
    
    # Chạy Flask app
    app.run(host='0.0.0.0', port=PORT)
