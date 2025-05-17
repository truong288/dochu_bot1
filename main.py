import re
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Biến toàn cục lưu trạng thái game
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

# Danh sách từ cấm (có thể mở rộng)
BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó","địt","mẹ","mày","lồn", "má"}

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "🎮 Game Nối Chữ đã sẵn sàng!\n"
        "📝 Các lệnh:\n"
        "/startgame - Bắt đầu trò chơi\n"
        "/join - Tham gia\n"
        "/reset - Đặt lại trò chơi\n"
        "/help - Hướng dẫn\n"
        "/begin - Bắt đầu sau khi đủ người\n"
        "/botplay - Chơi với bot"
    )

def start_game(update: Update, context: CallbackContext) -> None:
    if game_state["is_playing"]:
        update.message.reply_text("⚠️ Game đang chạy!")
        return

    game_state.update({
        "is_playing": True,
        "players": [],
        "used_words": [],
        "last_word": "",
        "current_player": None
    })
    update.message.reply_text("🎉 Game đã được khởi tạo! Gõ /join để tham gia.")

def join_game(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id in [p['id'] for p in game_state["players"]]:
        update.message.reply_text("⚠️ Bạn đã tham gia rồi!")
        return

    game_state["players"].append({"id": user.id, "name": user.full_name})
    update.message.reply_text(f"✅ {user.full_name} đã tham gia! Số người chơi: {len(game_state['players'])}")

def reset_game(update: Update, context: CallbackContext) -> None:
    game_state.update({
        "is_playing": False,
        "players": [],
        "used_words": [],
        "last_word": "",
        "current_player": None
    })
    update.message.reply_text("♻️ Game đã được reset!")

def begin_game(update: Update, context: CallbackContext) -> None:
    if len(game_state["players"]) < 2:
        update.message.reply_text("⚠️ Cần ít nhất 2 người chơi!")
        return

    game_state["current_player"] = random.choice(game_state["players"])
    game_state["start_time"] = datetime.now()
    update.message.reply_text(
        f"🔔 Game bắt đầu! Người ra từ đầu tiên là: {game_state['current_player']['name']}\n"
        f"📌 Gõ từ bất kỳ (VD: 'bầu trời') để bắt đầu nối chữ.\n"
        f"⏰ Mỗi lượt có 59 giây!"
    )

def bot_play(update: Update, context: CallbackContext) -> None:
    game_state["bot_playing"] = True
    start_game(update, context)
    join_game(update, context)
    game_state["players"].append({"id": 0, "name": "Bot 🤖"})
    update.message.reply_text("🤖 Bot đã tham gia! Gõ /begin để bắt đầu.")

def validate_word(word: str) -> bool:
    # Kiểm tra từ cấm
    if any(banned in word.lower() for banned in BANNED_WORDS):
        return False

    # Kiểm tra 2 từ có nghĩa (đơn giản)
    if len(word.split()) < 2:
        return False

    # Chặn tiếng Anh/số
    if re.search(r"[a-zA-Z0-9]", word):
        return False

    return True

def check_word_connection(last_word: str, new_word: str) -> bool:
    if not last_word:
        return True  # Từ đầu tiên
    return new_word.lower().startswith(last_word.split()[-1].lower())

def handle_message(update: Update, context: CallbackContext) -> None:
    if not game_state["is_playing"] or not game_state["current_player"]:
        return

    user = update.effective_user
    if user.id != game_state["current_player"]["id"]:
        return

    word = update.message.text.strip()
    
    # Kiểm tra từ hợp lệ
    if not validate_word(word):
        update.message.reply_text("❌ Từ không hợp lệ! Bị loại!")
        remove_player(user.id)
        return

    # Kiểm tra nối chữ
    if not check_word_connection(game_state["last_word"], word):
        update.message.reply_text("❌ Nối sai! Bị loại!")
        remove_player(user.id)
        return

    # Kiểm tra từ đã dùng
    if word.lower() in [w.lower() for w in game_state["used_words"]]:
        update.message.reply_text("❌ Từ đã dùng! Bị loại!")
        remove_player(user.id)
        return

    # Thêm từ mới
    game_state["used_words"].append(word)
    game_state["last_word"] = word
    next_player()

    # Thông báo lượt tiếp
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ {user.full_name} nối: '{word}'\n"
             f"👤 Lượt tiếp theo: {game_state['current_player']['name']}\n"
             f"⏰ Hết hạn lúc: {(datetime.now() + timedelta(seconds=59)).strftime('%H:%M:%S')}"
    )

    # Bot tự động chơi nếu có
    if game_state["bot_playing"] and game_state["current_player"]["id"] == 0:
        bot_word = generate_bot_word(word)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🤖 Bot nối: '{bot_word}'"
        )
        game_state["used_words"].append(bot_word)
        game_state["last_word"] = bot_word
        next_player()

def generate_bot_word(last_word: str) -> str:
    # Logic đơn giản: thêm 1 từ ngẫu nhiên hợp lệ
    sample_words = ["hoa quả", "quả táo", "táo bạo", "bạo lực", "lực lượng"]
    for w in sample_words:
        if w not in game_state["used_words"] and w.startswith(last_word.split()[-1]):
            return w
    return last_word.split()[-1] + " ... 🤖 Bot bí!"

def remove_player(player_id: int):
    game_state["players"] = [p for p in game_state["players"] if p["id"] != player_id]
    if len(game_state["players"]) == 1:
        end_game(winner=game_state["players"][0])
    else:
        next_player()

def next_player():
    current_idx = next((i for i, p in enumerate(game_state["players"]) 
                       if p["id"] == game_state["current_player"]["id"]), 0)
    next_idx = (current_idx + 1) % len(game_state["players"])
    game_state["current_player"] = game_state["players"][next_idx]
    game_state["start_time"] = datetime.now()

def end_game(winner: dict):
    # Cập nhật tổng chiến thắng
    game_state["winner_counts"][winner["id"]] = game_state["winner_counts"].get(winner["id"], 0) + 1
    
    # Thông báo kết quả
    winner_text = (
        f"🎉 CHIẾN THẮNG: {winner['name']}!\n"
        f"🏆 Tổng thắng: {game_state['winner_counts'][winner['id']]} lần"
    )
    if game_state["bot_playing"]:
        winner_text += "\n🤖 Bot đã bị đánh bại!" if winner["id"] != 0 else "\n🤖 Bot chiến thắng!"

    # Reset game
    reset_game(None, None)
    game_state["is_playing"] = False
    game_state["bot_playing"] = False
    
    # Gửi tin nhắn (cần pass context)
    from telegram import Bot
    bot = Bot(token="YOUR_BOT_TOKEN")
    bot.send_message(chat_id=game_state["players"][0]["id"], text=winner_text)

def main():
    updater = Updater("7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw")
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("startgame", start_game))
    dispatcher.add_handler(CommandHandler("join", join_game))
    dispatcher.add_handler(CommandHandler("reset", reset_game))
    dispatcher.add_handler(CommandHandler("begin", begin_game))
    dispatcher.add_handler(CommandHandler("botplay", bot_play))

    # Message handler
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
