import os
import logging
import asyncio
import re
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ================= CẤU HÌNH =================
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= TRẠNG THÁI GAME =================
class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.players = []
        self.current_phrase = ""
        self.used_phrases = set()
        self.current_player_index = 0
        self.in_game = False
        self.waiting_for_phrase = False
        self.win_counts = {}

game = GameState()
BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}

# ================= TIỆN ÍCH =================
def is_vietnamese(text):
    return bool(re.search(r'[àáạảãâầấậẩẫăắặẳẵêèéẹẻẽềếệểễìíịỉĩòóọỏõôồốộổỗơớợởỡùúụủũưứựửữỳýỵỷỹđ]', text.lower()))

def contains_bad_word(phrase):
    return any(bad_word in phrase.lower().split() for bad_word in BAD_WORDS)

# ================= HANDLERS =================
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game.reset()
    game.in_game = True
    await update.message.reply_text(
        "🎮 Bắt đầu trò chơi!\n"
        "👉 /join để tham gia\n"
        "👉 /begin để khởi động"
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in game.players:
        game.players.append(user.id)
        await update.message.reply_text(f"✅ {user.first_name} đã tham gia (Tổng: {len(game.players)})")
    else:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(game.players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi.")
        return
    
    game.waiting_for_phrase = True
    user_id = game.players[game.current_player_index]
    user = await context.bot.get_chat(user_id)
    await update.message.reply_text(
        f"✏️ {user.first_name}, hãy nhập cụm từ đầu tiên để bắt đầu!",
        parse_mode="HTML"
    )

async def play_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game.in_game or update.effective_user.id != game.players[game.current_player_index]:
        return
    
    text = update.message.text.strip().lower()
    
    # Validate input
    if not is_vietnamese(text):
        await eliminate_player(update, context, "Không dùng tiếng Việt.")
        return
    
    words = text.split()
    if len(words) != 2:
        await eliminate_player(update, context, "Phải gồm đúng 2 từ.")
        return
    
    if contains_bad_word(text):
        await eliminate_player(update, context, "Từ ngữ không phù hợp.")
        return
    
    if text in game.used_phrases:
        await eliminate_player(update, context, "Cụm từ đã dùng.")
        return
    
    if not game.waiting_for_phrase and words[0] != game.current_phrase.split()[-1]:
        await eliminate_player(update, context, "Không đúng từ nối.")
        return
    
    # Update game state
    game.used_phrases.add(text)
    game.current_phrase = text
    game.waiting_for_phrase = False
    game.current_player_index = (game.current_player_index + 1) % len(game.players)
    
    if len(game.players) == 1:
        await declare_winner(context, game.players[0])
        return
    
    next_id = game.players[game.current_player_index]
    next_player = await context.bot.get_chat(next_id)
    await update.message.reply_text(
        f"✅ Hợp lệ!\n➡️ Từ tiếp theo: '{game.current_phrase.split()[-1]}'\n"
        f"👤 Lượt của {next_player.first_name}",
        parse_mode="HTML"
    )

async def eliminate_player(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str):
    user = update.effective_user
    game.players.remove(user.id)
    await update.message.reply_text(f"❌ {user.first_name} bị loại! Lý do: {reason}")
    
    if len(game.players) == 1:
        await declare_winner(context, game.players[0])
    elif game.players:
        next_id = game.players[game.current_player_index % len(game.players)]
        next_player = await context.bot.get_chat(next_id)
        await update.message.reply_text(f"👤 {next_player.first_name}, tiếp tục!")

async def declare_winner(context: ContextTypes.DEFAULT_TYPE, winner_id: int):
    game.win_counts[winner_id] = game.win_counts.get(winner_id, 0) + 1
    winner = await context.bot.get_chat(winner_id)
    await context.bot.send_message(
        chat_id=winner_id,
        text=f"🏆 {winner.first_name} THẮNG CUỘC! Tổng thắng: {game.win_counts[winner_id]}"
    )
    game.reset()

# ================= FLASK APP =================
app = Flask(__name__)

# Khởi tạo Telegram Application
def init_telegram_app():
    application = Application.builder() \
        .token(TOKEN) \
        .pool_timeout(30) \
        .connect_timeout(30) \
        .build()
    
    # Đăng ký handlers
    application.add_handler(CommandHandler("start", start_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("begin", begin_game))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))
    
    return application

telegram_app = init_telegram_app()

@app.route('/')
def home():
    return "Bot đang hoạt động!"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Xử lý update từ Telegram
        json_data = request.get_json()
        update = Update.de_json(json_data, telegram_app.bot)
        
        # Tạo event loop mới
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(telegram_app.process_update(update))
        finally:
            loop.close()
            
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Lỗi webhook: {e}", exc_info=True)
        return jsonify({"status": "error"}), 500

# ================= MAIN =================
async def initialize():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    logger.info("Bot đã sẵn sàng nhận lệnh!")

if __name__ == '__main__':
    # Khởi tạo và chạy ứng dụng
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(initialize())
        app.run(host='0.0.0.0', port=PORT)
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(telegram_app.shutdown())
        loop.close()
