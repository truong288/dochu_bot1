from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from stay_alive import keep_alive
import asyncio
import re
import json
import os
from datetime import datetime
import aiohttp

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

# Dictionary API (using VietDict)
DICT_API_URL = "https://api.vietdict.info/word"
HEADERS = {"User-Agent": "Telegram Nối Chữ Bot"}

# Banned words
BANNED_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày","chi","mô","răng","rứa", "má"}

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
    global players, player_names, current_phrase, used_phrases, current_player_index, in_game, waiting_for_phrase, turn_timeout_task, game_start_time
    players = []
    player_names = {}
    current_phrase = ""
    used_phrases = {}
    current_player_index = 0
    in_game = False
    waiting_for_phrase = False
    game_start_time = None
    if turn_timeout_task:
        turn_timeout_task.cancel()
        turn_timeout_task = None

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game_state()
    global stats
    stats = {}
    save_stats(stats)
    await update.message.reply_text("✅ Trò chơi và bảng xếp hạng đã được reset!")

async def check_word_in_dictionary(word):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DICT_API_URL}/{word}", headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    return bool(data.get("meanings"))
                return False
    except Exception as e:
        print(f"Dictionary API error: {e}")
        return True  # If API fails, assume word is valid to keep game going

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

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game_state()
    global in_game, game_start_time
    in_game = True
    game_start_time = get_current_time()
    await update.message.reply_text(
       "🎮 Trò chơi bắt đầu!\n"
        "👉 Gõ /join Để tham gia\n"
        "👉 Gõ /begin Khi đủ người, để bắt đầu\n\n"
        "📚 Từ điển đã được kích hoạt để kiểm tra từ hợp lệ!"
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players
    user = update.effective_user
    if user.id not in players:
        players.append(user.id)
        get_player_name(user)
        await update.message.reply_text(f"✅ {get_player_name(user)} Đã tham gia! (Tổng: {len(players)} Ng)")
    else:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_for_phrase, current_player_index
    if len(players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi để bắt đầu!")
        return
    
    waiting_for_phrase = True
    current_player_index = 0
    user_id = players[current_player_index]
    user = await context.bot.get_chat(user_id)
    await update.message.reply_text(
        f"✏️ {get_player_name(user)}, Hãy nhập cụm từ đầu tiên:...\n"
        f"⏰ Bạn có: 60 giây\n"
        f"📌 Yêu cầu: 2 từ tiếng Việt có nghĩa"
    )
    await start_turn_timer(context)

async def play_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_phrase, current_player_index, used_phrases, players, in_game, waiting_for_phrase, turn_timeout_task
    
    if not in_game:
        return

    user = update.effective_user
    if user.id not in players:
        return
        
    if user.id != players[current_player_index]:
        return

    text = update.message.text.strip().lower()

    # Basic validation
    if not is_vietnamese(text):
        await eliminate_player(update, context, "Không hợp lệ (phải là 2 từ tiếng Việt)")
        return

    if contains_banned_words(text):
        await eliminate_player(update, context, "Không hợp lệ (chứa từ cấm)")
        return

    # Check first word in dictionary
    first_word = text.split()[0]
    if not waiting_for_phrase and first_word != current_phrase.split()[-1]:
        await eliminate_player(update, context, f"Từ đầu phải là: '{current_phrase.split()[-1]}'")
        return

    # Check if phrase already used
    if text in used_phrases:
        await eliminate_player(update, context, "Cụm từ đã dùng")
        return

    # Dictionary validation for both words
    valid = await check_word_in_dictionary(text.split()[0])
    if not valid:
        await eliminate_player(update, context, f"Từ '{text.split()[0]}' không có trong từ điển")
        return
        
    valid = await check_word_in_dictionary(text.split()[1])
    if not valid:
        await eliminate_player(update, context, f"Từ '{text.split()[1]}' không có trong từ điển")
        return

    # If all checks passed
    used_phrases[text] = 1
    current_phrase = text
    
    if waiting_for_phrase:
        waiting_for_phrase = False
        await process_valid_word(update, context, text, is_first_word=True)
    else:
        await process_valid_word(update, context, text)

async def process_valid_word(update, context, text, is_first_word=False):
    global current_player_index, players, turn_timeout_task
    
    if turn_timeout_task:
        turn_timeout_task.cancel()
    
    if is_first_word:
        message = f"🎯 Từ bắt đầu: '{text}'\n\n"
    else:
        message = f"✅ {get_player_name(update.effective_user)} Đã nối thành công!\n\n"
    
    current_player_index = (current_player_index + 1) % len(players)
    
    if len(players) == 1:
        await announce_winner(update, context)
        return
    
    current_word = current_phrase.split()[-1]
    next_user = await context.bot.get_chat(players[current_player_index])
    
    # Get word definition for educational purpose
    definition = await get_word_definition(current_word)
    definition_msg = f"\n📖 {current_word}: {definition}\n" if definition else ""
    
    await update.message.reply_text(
        f"{message}"
        f"{definition_msg}"
        f"🔄 Lượt tiếp theo:\n"
        f"👉 Từ cần nối: 『{current_word}』\n"
        f"👤 Người chơi: {get_player_name(next_user)}\n"
        f"⏳ Thời gian: 60 giây "
    )
    
    await start_turn_timer(context)

async def get_word_definition(word):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DICT_API_URL}/{word}", headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("meanings"):
                        # Get the first short definition
                        first_meaning = data["meanings"][0]
                        return first_meaning.get("definition", "")
        return ""
    except Exception:
        return ""

async def eliminate_player(update, context, reason):
    global players, current_player_index, turn_timeout_task
    
    user = update.effective_user
    user_name = get_player_name(user)
    player_index = players.index(user.id)
    
    if turn_timeout_task:
        turn_timeout_task.cancel()
    
    await update.message.reply_text(f"❌ {user_name} bị loại! Lý do: {reason}")
    players.remove(user.id)
    
    if len(players) == 1:
        await announce_winner(update, context)
        return
        
    if player_index < current_player_index:
        current_player_index -= 1
    elif player_index == current_player_index and current_player_index >= len(players):
        current_player_index = 0
    
    current_word = current_phrase.split()[-1]
    next_user = await context.bot.get_chat(players[current_player_index])
    
    # Get word definition
    definition = await get_word_definition(current_word)
    definition_msg = f"\n📖 {current_word}: {definition}\n" if definition else ""
    
    await update.message.reply_text(
        f"{definition_msg}"
        f"👥 Người chơi còn lại: {len(players)}\n"
        f"🔄 Lượt tiếp theo:\n"
        f"👉 Từ cần nối: 『{current_word}』\n"
        f"👤 Người chơi: {get_player_name(next_user)}\n"
        f"⏳ Thời gian: 60 giây "
    )
    await start_turn_timer(context)

async def announce_winner(update, context):
    if not players:
        await context.bot.send_message(
            chat_id=update.effective_chat.id if update else context._chat_id,
            text="🏁 Trò chơi kết thúc, không có người chiến thắng!"
        )
        reset_game_state()
        return
    
    winner_id = players[0]
    winner = await context.bot.get_chat(winner_id)
    winner_name = get_player_name(winner)
    
    stats[winner_name] = stats.get(winner_name, 0) + 1
    save_stats(stats)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id if update else context._chat_id,
        text=f"🏆 CHIẾN THẮNG! 🏆\n"
             f"👑 {winner_name}:\u2003\u2003 Vô Địch Nối Chữ!\n"
             f"📊 Số lần thắng:\u2003 {stats[winner_name]}"
    )
    reset_game_state()

async def start_turn_timer(context):
    global turn_timeout_task
    if turn_timeout_task:
        turn_timeout_task.cancel()
    turn_timeout_task = asyncio.create_task(turn_timer(context))

async def turn_timer(context):
    global players, current_player_index
    
    try:
        await asyncio.sleep(60)
        
        if not players or current_player_index >= len(players):
            return
            
        user_id = players[current_player_index]
        user = await context.bot.get_chat(user_id)
        user_name = get_player_name(user)
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"⏰ {user_name} Hết giờ: Loại!"
        )
        
        eliminated_index = current_player_index
        players.remove(user_id)
        
        if len(players) == 1:
            await announce_winner(None, context)
            return
            
        if eliminated_index < current_player_index:
            current_player_index -= 1
        elif eliminated_index == current_player_index and current_player_index >= len(players):
            current_player_index = 0
        
        current_word = current_phrase.split()[-1]
        next_user = await context.bot.get_chat(players[current_player_index])
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"👥 Người chơi còn lại: {len(players)}\n"
                 f"🔄 Lượt tiếp theo:\n"
                 f"👉 Từ cần nối: 『{current_word}』\n"
                 f"👤 Người chơi: {get_player_name(next_user)}\n"
                 f"⏳ Thời gian: 60 giây "
        )
        await start_turn_timer(context)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Lỗi timer: {e}")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not stats:
        await update.message.reply_text("📊 Chưa có ai thắng cả!")
        return
    
    ranking = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    message = "🏆 BẢNG XẾP HẠNG 🏆\n\n"
    for i, (name, wins) in enumerate(ranking[:10], 1):
        message += f"{i}. {name}: {wins} lần thắng\n"
    
    await update.message.reply_text(message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 HƯỚNG DẪN TRÒ CHƠI NỐI CHỮ\n\n"
        "🔹 /startgame - Bắt đầu trò chơi mới\n"
        "🔹 /join - Tham gia trò chơi\n"
        "🔹 /begin - Bắt đầu khi đủ người\n"
        "🔹 /win - Xem bảng xếp hạng\n"
        "🔹 /reset - Reset trò chơi\n"
        "🔹 /help - Xem hướng dẫn\n\n"
        "📌 LUẬT CHƠI:\n"
        "- Mỗi cụm từ gồm 2 từ tiếng Việt có nghĩa\n"
        "- Nối từ cuối của cụm trước đó\n"
        "- Không lặp lại cụm từ đã dùng\n"
        "- Không dùng từ cấm hoặc không phù hợp\n"
        "- Từ phải có trong từ điển tiếng Việt\n"
        "- Mỗi lượt có 60 giây để trả lời\n"
        "- Người cuối cùng còn lại sẽ chiến thắng!\n\n"
        "📚 TÍNH NĂNG MỚI:\n"
        "- Kiểm tra từ bằng từ điển tiếng Việt\n"
        "- Hiển thị định nghĩa từ sau mỗi lượt chơi"
    )

if __name__ == '__main__':
    TOKEN = "7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw"  # Thay bằng token thật
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("begin", begin_game))
    app.add_handler(CommandHandler("win", show_stats))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))
    
    print("Bot đang chạy...")
    app.run_polling()
