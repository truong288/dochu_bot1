import re
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Game state
game_state = {
    "is_playing": False,
    "players": [],
    "current_player": None,
    "used_words": [],
    "last_word": "",
    "start_time": None,
    "winner_counts": {},
    "bot_playing": False
}

# Banned words
BANNED_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "lồn", "má"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 Game Nối Chữ đã sẵn sàng!\n"
        "📝 Các lệnh:\n"
        "/startgame - Bắt đầu trò chơi\n"
        "/join - Tham gia\n"
        "/reset - Đặt lại trò chơi\n"
        "/help - Hướng dẫn\n"
        "/begin - Bắt đầu sau khi đủ người\n"
        "/botplay - Chơi với bot"
    )

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if game_state["is_playing"]:
        await update.message.reply_text("⚠️ Game đang chạy!")
        return

    game_state.update({
        "is_playing": True,
        "players": [],
        "used_words": [],
        "last_word": "",
        "current_player": None
    })
    await update.message.reply_text("🎉 Game đã được khởi tạo! Gõ /join để tham gia.")

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id in [p['id'] for p in game_state["players"]]:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")
        return

    game_state["players"].append({"id": user.id, "name": user.full_name})
    await update.message.reply_text(f"✅ {user.full_name} đã tham gia! Số người chơi: {len(game_state['players'])}")

async def reset_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_state.update({
        "is_playing": False,
        "players": [],
        "used_words": [],
        "last_word": "",
        "current_player": None
    })
    await update.message.reply_text("♻️ Game đã được reset!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(game_state["players"]) < 2:
        await update.message.reply_text("⚠️ Cần ít nhất 2 người chơi!")
        return

    game_state["current_player"] = random.choice(game_state["players"])
    game_state["start_time"] = datetime.now()
    await update.message.reply_text(
        f"🔔 Game bắt đầu! Người ra từ đầu tiên là: {game_state['current_player']['name']}\n"
        f"📌 Gõ từ bất kỳ (VD: 'bầu trời') để bắt đầu nối chữ.\n"
        f"⏰ Mỗi lượt có 59 giây!"
    )

async def bot_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_state["bot_playing"] = True
    await start_game(update, context)
    await join_game(update, context)
    game_state["players"].append({"id": 0, "name": "Bot 🤖"})
    await update.message.reply_text("🤖 Bot đã tham gia! Gõ /begin để bắt đầu.")

def validate_word(word: str) -> bool:
    if any(banned in word.lower() for banned in BANNED_WORDS):
        return False
    if len(word.split()) < 2:
        return False
    if re.search(r"[a-zA-Z0-9]", word):
        return False
    return True

def check_word_connection(last_word: str, new_word: str) -> bool:
    if not last_word:
        return True
    return new_word.lower().startswith(last_word.split()[-1].lower())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not game_state["is_playing"] or not game_state["current_player"]:
        return

    user = update.effective_user
    if user.id != game_state["current_player"]["id"]:
        return

    word = update.message.text.strip()
    
    if not validate_word(word):
        await update.message.reply_text("❌ Từ không hợp lệ! Bị loại!")
        await remove_player(user.id)
        return

    if not check_word_connection(game_state["last_word"], word):
        await update.message.reply_text("❌ Nối sai! Bị loại!")
        await remove_player(user.id)
        return

    if word.lower() in [w.lower() for w in game_state["used_words"]]:
        await update.message.reply_text("❌ Từ đã dùng! Bị loại!")
        await remove_player(user.id)
        return

    game_state["used_words"].append(word)
    game_state["last_word"] = word
    await next_player()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ {user.full_name} nối: '{word}'\n"
             f"👤 Lượt tiếp theo: {game_state['current_player']['name']}\n"
             f"⏰ Hết hạn lúc: {(datetime.now() + timedelta(seconds=59)).strftime('%H:%M:%S')}"
    )

    if game_state["bot_playing"] and game_state["current_player"]["id"] == 0:
        bot_word = generate_bot_word(word)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🤖 Bot nối: '{bot_word}'"
        )
        game_state["used_words"].append(bot_word)
        game_state["last_word"] = bot_word
        await next_player()

def generate_bot_word(last_word: str) -> str:
    sample_words = ["hoa quả", "quả táo", "táo bạo", "bạo lực", "lực lượng"]
    for w in sample_words:
        if w not in game_state["used_words"] and w.startswith(last_word.split()[-1]):
            return w
    return last_word.split()[-1] + " ... 🤖 Bot bí!"

async def remove_player(player_id: int):
    game_state["players"] = [p for p in game_state["players"] if p["id"] != player_id]
    if len(game_state["players"]) == 1:
        await end_game(winner=game_state["players"][0])
    else:
        await next_player()

async def next_player():
    current_idx = next((i for i, p in enumerate(game_state["players"]) 
                       if p["id"] == game_state["current_player"]["id"]), 0)
    next_idx = (current_idx + 1) % len(game_state["players"])
    game_state["current_player"] = game_state["players"][next_idx]
    game_state["start_time"] = datetime.now()

async def end_game(winner: dict):
    game_state["winner_counts"][winner["id"]] = game_state["winner_counts"].get(winner["id"], 0) + 1
    
    winner_text = (
        f"🎉 CHIẾN THẮNG: {winner['name']}!\n"
        f"🏆 Tổng thắng: {game_state['winner_counts'][winner['id']]} lần"
    )
    if game_state["bot_playing"]:
        winner_text += "\n🤖 Bot đã bị đánh bại!" if winner["id"] != 0 else "\n🤖 Bot chiến thắng!"

    game_state["is_playing"] = False
    game_state["bot_playing"] = False
    
    await context.bot.send_message(
        chat_id=winner["id"],
        text=winner_text
    )

def main() -> None:
    application = Application.builder().token("7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("reset", reset_game))
    application.add_handler(CommandHandler("begin", begin_game))
    application.add_handler(CommandHandler("botplay", bot_play))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
