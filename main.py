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

# Config
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Game State
players = []
current_phrase = ""
used_phrases = {}
current_player_index = 0
in_game = False
waiting_for_phrase = False
turn_timeout_task = None
win_counts = {}

BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}

def reset_game():
    global players, current_phrase, used_phrases, current_player_index, in_game, waiting_for_phrase, turn_timeout_task
    players = []
    current_phrase = ""
    used_phrases = {}
    current_player_index = 0
    in_game = False
    waiting_for_phrase = False
    if turn_timeout_task:
        turn_timeout_task.cancel()
        turn_timeout_task = None

def is_vietnamese(text):
    return bool(re.search(r'[àáạảãâầấậẩẫăắặẳẵêèéẹẻẽềếệểễìíịỉĩòóọỏõôồốộổỗơớợởỡùúụủũưứựửữỳýỵỷỹđ]', text))

def contains_bad_word(phrase):
    return any(bad in phrase.split() for bad in BAD_WORDS)

def is_valid_phrase(phrase):
    return True

# Handlers
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
    global current_phrase, current_player_index, used_phrases, players, in_game, waiting_for_phrase
    if not in_game:
        return
    user = update.effective_user
    text = update.message.text.strip().lower()
    if user.id != players[current_player_index]:
        return
    
    # Validation checks...
    # (Giữ nguyên phần validation từ code gốc)

    used_phrases[text] = 1
    current_phrase = text
    waiting_for_phrase = False
    current_player_index = (current_player_index + 1) % len(players)

    if len(players) == 1:
        await declare_winner(context, players[0])
        return

    next_id = players[current_player_index]
    next_chat = await context.bot.get_chat(next_id)
    mention = f"<a href='tg://user?id={next_id}'>{next_chat.first_name}</a>"
    await update.message.reply_text(
        f"✅ Hợp lệ!\n➡️ Từ tiếp theo bắt đầu bằng: '{current_phrase.split()[-1]}'\nTới lượt {mention}",
        parse_mode="HTML")
    await start_turn_timer(context)

# Flask App
app = Flask(__name__)

# Khởi tạo Application
def init_bot_app():
    application = Application.builder().token(TOKEN).build()
    
    # Đăng ký handlers
    application.add_handler(CommandHandler("start", start_game))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("begin", begin_game))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))
    
    return application

bot_app = init_bot_app()

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # 1. Khởi tạo application nếu chưa có
        if not bot_app:
            bot_app = init_bot_app()
            asyncio.run(bot_app.initialize())
        
        # 2. Xử lý update
        json_data = request.get_json()
        update = Update.de_json(json_data, bot_app.bot)
        asyncio.run(bot_app.process_update(update))
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    return "Bot is running!"

async def set_webhook():
    await bot_app.bot.set_webhook(WEBHOOK_URL)

if __name__ == '__main__':
    # Khởi tạo bot và set webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize application
        loop.run_until_complete(bot_app.initialize())
        
        # Set webhook
        loop.run_until_complete(set_webhook())
        
        # Start Flask
        app.run(host='0.0.0.0', port=PORT)
    
    finally:
        loop.run_until_complete(bot_app.shutdown())
        loop.close()
