from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from stay_alive import keep_alive
import asyncio
import re
import json
import os
import random
import requests
from datetime import datetime

keep_alive()

# Game state
players = []
player_names = {}
current_phrase = ""
used_phrases = {}
current_player_index = 0
in_game = False
waiting_for_phrase = False
turn_timeout_task = None
game_start_time = None
playing_with_bot = False

# Banned words
BANNED_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày","chi","mô","răng","rứa", "má"}

# Bot data
BOT_ID = @NOICHU1_BOT  # Thay bằng bot ID thực tế
BOT_NAME = "Bot 🤖"

# API Từ điển tiếng Việt
DICTIONARY_API = "https://api.tudien.com/v1/words"  # Thay bằng API thực tế

# Stats
STATS_FILE = "winners.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

stats = load_stats()

def reset_game_state():
    global players, player_names, current_phrase, used_phrases, current_player_index, in_game, waiting_for_phrase, turn_timeout_task, game_start_time, playing_with_bot
    players = []
    player_names = {}
    current_phrase = ""
    used_phrases = {}
    current_player_index = 0
    in_game = False
    waiting_for_phrase = False
    game_start_time = None
    playing_with_bot = False
    if turn_timeout_task:
        turn_timeout_task.cancel()
        turn_timeout_task = None

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game_state()
    global stats
    stats = {}
    save_stats(stats)
    await update.message.reply_text("✅ Trò chơi và bảng xếp hạng đã được reset!")

def is_vietnamese(text):
    text = text.strip().lower()
    if len(text.split()) != 2:
        return False
    if re.search(r'[0-9]', text):
        return False
    if re.search(r'[a-zA-Z]', text) and not re.search(r'[à-ỹ]', text):
        return False
    return True

def contains_banned_words(text):
    words = text.lower().split()
    return any(word in BANNED_WORDS for word in words)

def get_player_name(user):
    if user.id in player_names:
        return player_names[user.id]
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"
    player_names[user.id] = name
    return name

def get_current_time():
    return datetime.now().strftime("%H:%M")

async def get_word_from_api(last_word=None):
    """Lấy từ có nghĩa từ API từ điển"""
    try:
        if last_word:
            params = {"starts_with": last_word, "limit": 50}
        else:
            params = {"random": True, "limit": 50}
        
        response = requests.get(DICTIONARY_API, params=params, timeout=5)
        data = response.json()
        
        if data and "words" in data:
            return random.choice(data["words"])
        return None
    except:
        return None

async def generate_meaningful_phrase(last_word=None):
    """Tạo cụm từ có nghĩa"""
    if last_word:
        # Tìm từ tiếp theo có nghĩa
        next_word = await get_word_from_api(last_word)
        if next_word:
            return f"{last_word} {next_word}"
    else:
        # Tạo cụm từ mới ngẫu nhiên
        first_word = await get_word_from_api()
        if first_word:
            second_word = await get_word_from_api(first_word)
            if second_word:
                return f"{first_word} {second_word}"
    
    # Fallback nếu API không hoạt động
    vietnamese_words = ["hoa hồng", "mặt trời", "biển cả", "núi non", "sông dài"]
    return random.choice(vietnamese_words)

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game_state()
    global in_game, game_start_time
    in_game = True
    game_start_time = get_current_time()
    await update.message.reply_text(
       "🎮 Trò chơi bắt đầu!\n"
        "👉 Gõ /join Để tham gia\n"
        "👉 Gõ /begin Khi đủ người, để bắt đầu\n"
        "👉 Hoặc gõ /playwithbot để chơi với bot"
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, playing_with_bot
    if playing_with_bot:
        await update.message.reply_text("⚠️ Bạn đang chơi với bot, không thể tham gia!")
        return
        
    user = update.effective_user
    if user.id not in players:
        players.append(user.id)
        get_player_name(user)
        await update.message.reply_text(f"✅ {get_player_name(user)} Đã tham gia! (Tổng: {len(players)} Ng)")
    else:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")

async def play_with_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, playing_with_bot
    if len(players) > 0:
        await update.message.reply_text("⚠️ Đã có người chơi tham gia, không thể chơi với bot!")
        return
        
    reset_game_state()
    user = update.effective_user
    players.append(user.id)
    players.append(BOT_ID)
    player_names[BOT_ID] = BOT_NAME
    playing_with_bot = True
    
    await update.message.reply_text(
        "🤖 Bắt đầu chơi với Bot thông minh!\n"
        "Bot sẽ sử dụng từ điển tiếng Việt để chơi\n"
        "👉 Gõ /begin để bắt đầu trò chơi"
    )

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_for_phrase, current_player_index, playing_with_bot
    
    if len(players) < 1:
        await update.message.reply_text("❗ Cần ít nhất 1 người chơi để bắt đầu!")
        return
    
    if len(players) == 1 and not playing_with_bot:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi hoặc chơi với bot (/playwithbot)!")
        return
    
    waiting_for_phrase = True
    current_player_index = 0
    user_id = players[current_player_index]
    
    if user_id == BOT_ID:
        await bot_turn(context)
        return
        
    user = await context.bot.get_chat(user_id)
    await update.message.reply_text(
        f"✏️ {get_player_name(user)}, Hãy nhập cụm từ đầu tiên (2 từ tiếng Việt có nghĩa):\n"
        f"⏰ Bạn có 60 giây"
    )
    await start_turn_timer(context)

async def bot_turn(context):
    global current_phrase, used_phrases, current_player_index, players
    
    try:
        # Tạo cụm từ có nghĩa dựa trên từ cuối cùng
        last_word = current_phrase.split()[-1] if current_phrase else None
        bot_phrase = await generate_meaningful_phrase(last_word)
        
        # Đảm bảo cụm từ chưa được dùng
        max_attempts = 5
        attempts = 0
        while bot_phrase in used_phrases and attempts < max_attempts:
            bot_phrase = await generate_meaningful_phrase(last_word)
            attempts += 1
            
        if attempts == max_attempts:
            raise Exception("Không tìm được từ mới")
        
        # Simulate bot thinking
        await asyncio.sleep(2)
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"🤖 {BOT_NAME} nói: 『{bot_phrase}』"
        )
        
        current_phrase = bot_phrase
        used_phrases[bot_phrase] = 1
        current_player_index = (current_player_index + 1) % len(players)
        
        if len(players) == 1:
            await announce_winner(None, context)
            return
        
        # Next player's turn
        next_user_id = players[current_player_index]
        if next_user_id == BOT_ID:
            await bot_turn(context)
        else:
            next_user = await context.bot.get_chat(next_user_id)
            current_word = current_phrase.split()[-1]
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=f"🔄 Lượt tiếp theo:\n"
                     f"👉 Từ cần nối: 『{current_word}』\n"
                     f"👤 Người chơi: {get_player_name(next_user)}\n"
                     f"⏳ Thời gian: 60 giây"
            )
            await start_turn_timer(context)
            
    except Exception as e:
        print(f"Bot error: {e}")
        await context.bot.send_message(
            chat_id=context._chat_id,
            text="🤖 Bot không tìm được từ phù hợp! Bot bị loại!"
        )
        players.remove(BOT_ID)
        if len(players) == 1:
            await announce_winner(None, context)

# ... (giữ nguyên các hàm play_word, process_valid_word, eliminate_player, 
# announce_winner, start_turn_timer, turn_timer, show_stats, help_command)

if __name__ == '__main__':
    TOKEN = "7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw"  # Thay bằng token thật
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("playwithbot", play_with_bot))
    app.add_handler(CommandHandler("begin", begin_game))
    app.add_handler(CommandHandler("win", show_stats))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))
    
    print("Bot đang chạy...")
    app.run_polling()
