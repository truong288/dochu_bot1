import re
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import requests

# ===== CẤU HÌNH =====
BOT_TOKEN = "7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw"  # 👈 Thay bằng token bot thật của bạn!
DICTIONARY_API = "https://api.tudien.com/check"  # API từ điển

# Từ cấm
BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}

# ===== LỚP QUẢN LÝ GAME =====
class GameManager:
    def __init__(self):
        self.players: List[Dict] = []
        self.current_phrase: str = ""
        self.used_phrases: Dict[str, int] = {}
        self.current_player_index: int = 0
        self.in_game: bool = False
        self.waiting_for_phrase: bool = False
        self.turn_timeout_task: Optional[asyncio.Task] = None
        self.bot_playing: bool = False
        self.winner_counts: Dict[int, int] = {}

    def reset(self):
        """Reset trạng thái game"""
        self.players = []
        self.current_phrase = ""
        self.used_phrases = {}
        self.current_player_index = 0
        self.in_game = False
        self.waiting_for_phrase = False
        if self.turn_timeout_task:
            self.turn_timeout_task.cancel()
        self.bot_playing = False

    def add_player(self, user_id: int, username: str):
        """Thêm người chơi mới"""
        if user_id not in [p["id"] for p in self.players]:
            self.players.append({"id": user_id, "name": username})

    def next_player(self):
        """Chuyển lượt cho người chơi tiếp theo"""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        return self.players[self.current_player_index]

    def remove_player(self, user_id: int):
        """Loại bỏ người chơi"""
        self.players = [p for p in self.players if p["id"] != user_id]
        if self.current_player_index >= len(self.players):
            self.current_player_index = 0

# ===== KHỞI TẠO =====
game = GameManager()

# ===== TIỆN ÍCH KIỂM TRA =====
def contains_bad_word(text: str) -> bool:
    """Kiểm tra từ cấm"""
    text_lower = text.lower()
    return any(bad_word in text_lower for bad_word in BAD_WORDS)

def is_vietnamese(text: str) -> bool:
    """Kiểm tra có phải tiếng Việt không"""
    vietnamese_pattern = re.compile(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        re.IGNORECASE
    )
    return bool(vietnamese_pattern.search(text))

async def check_dictionary(word: str) -> Tuple[bool, Optional[str]]:
    """
    Kiểm tra từ có tồn tại trong từ điển không
    Trả về: (is_valid, error_message)
    """
    try:
        response = await asyncio.to_thread(
            requests.get,
            DICTIONARY_API,
            params={"word": word},
            timeout=3
        )
        
        if response.status_code == 200:
            data = response.json()
            return (data.get("valid", True), None)
        
        return False, "Không kết nối được từ điển"
        
    except Exception as e:
        print(f"Lỗi API từ điển: {e}")
        return True, None  # Cho qua nếu API lỗi

async def validate_phrase(phrase: str) -> Tuple[bool, Optional[str]]:
    """Kiểm tra cụm từ hợp lệ"""
    words = phrase.strip().split()
    
    # Kiểm tra cơ bản
    if len(words) != 2:
        return False, "Phải nhập chính xác 2 từ"
    
    if contains_bad_word(phrase):
        return False, "Chứa từ cấm"
    
    if not is_vietnamese(phrase):
        return False, "Phải dùng tiếng Việt"
    
    # Kiểm tra từ điển (bất đồng bộ)
    for word in words:
        is_valid, error = await check_dictionary(word)
        if not is_valid:
            return False, f"Từ '{word}' không tồn tại trong từ điển"
    
    return True, None

# ===== HANDLER LỆNH =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start - Hướng dẫn"""
    await update.message.reply_text(
        "🎮 Game Nối Chữ - Luật chơi:\n"
        "1. Mỗi người nhập cụm từ 2 từ\n"
        "2. Từ đầu phải nối với từ cuối của người trước\n"
        "3. Không dùng từ cấm hoặc vô nghĩa\n\n"
        "📝 Lệnh:\n"
        "/startgame - Bắt đầu game\n"
        "/join - Tham gia\n"
        "/botplay - Chơi với bot\n"
        "/begin - Bắt đầu khi đủ người\n"
        "/help - Xem hướng dẫn"
    )

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /startgame - Khởi tạo game"""
    game.reset()
    game.in_game = True
    await update.message.reply_text(
        "🎉 Game đã được khởi tạo!\n"
        "👉 Gõ /join để tham gia\n"
        "👉 Gõ /botplay để thêm bot"
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /join - Tham gia game"""
    user = update.effective_user
    game.add_player(user.id, user.full_name)
    await update.message.reply_text(
        f"✅ {user.full_name} đã tham gia! (Tổng: {len(game.players)} người)"
    )

async def bot_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /botplay - Thêm bot vào game"""
    game.bot_playing = True
    game.add_player(0, "Bot 🤖")
    await update.message.reply_text("🤖 Bot đã tham gia!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /begin - Bắt đầu game"""
    if len(game.players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi!")
        return
    
    game.waiting_for_phrase = True
    current_player = game.players[game.current_player_index]
    
    if current_player["id"] == 0:  # Bot đi đầu
        await bot_turn(context)
        return
    
    # Người chơi đi đầu
    mention = f"<a href='tg://user?id={current_player['id']}'>@{current_player['name']}</a>"
    await update.message.reply_text(
        f"✏️ {mention}, hãy nhập cụm từ đầu tiên! (2 từ)",
        parse_mode="HTML"
    )
    await start_turn_timer(context)

# ===== XỬ LÝ GAME CHÍNH =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn người chơi"""
    if not game.in_game:
        return
    
    user = update.effective_user
    current_player = game.players[game.current_player_index] if game.players else None
    
    # Kiểm tra lượt chơi
    if not current_player or user.id != current_player["id"]:
        return
    
    text = update.message.text.strip()
    is_valid, error = await validate_phrase(text)
    
    if not is_valid:
        await update.message.reply_text(f"❌ Lỗi: {error}")
        await eliminate_player(update, context)
        return
    
    # Xử lý khi hợp lệ
    if game.waiting_for_phrase:  # Lượt đầu
        game.current_phrase = text
        game.used_phrases[text.lower()] = 1
        game.waiting_for_phrase = False
    else:  # Các lượt tiếp theo
        if text.lower().split()[0] != game.current_phrase.split()[-1].lower():
            await update.message.reply_text("❌ Không đúng từ nối!")
            await eliminate_player(update, context)
            return
        
        if text.lower() in game.used_phrases:
            await update.message.reply_text("❌ Cụm từ đã được dùng!")
            await eliminate_player(update, context)
            return
        
        game.used_phrases[text.lower()] = 1
        game.current_phrase = text
    
    # Chuyển lượt
    game.next_player()
    
    # Kiểm tra kết thúc game
    if len(game.players) == 1:
        await end_game(context)
        return
    
    # Xử lý lượt tiếp theo
    next_player = game.players[game.current_player_index]
    
    if next_player["id"] == 0:  # Bot chơi
        await bot_turn(context)
        return
    
    # Người chơi tiếp theo
    mention = f"<a href='tg://user?id={next_player['id']}'>@{next_player['name']}</a>"
    last_word = game.current_phrase.split()[-1]
    await update.message.reply_text(
        f"✅ Đã cập nhật!\n"
        f"👤 Lượt tiếp: {mention}\n"
        f"🔗 Nối từ: '{last_word}'\n"
        f"⏰ Hạn: 59 giây",
        parse_mode="HTML"
    )
    await start_turn_timer(context)

async def bot_turn(context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lượt chơi của bot"""
    if not game.current_phrase:  # Lượt đầu
        bot_phrase = "bầu trời"  # Từ mặc định cho bot
    else:
        last_word = game.current_phrase.split()[-1]
        bot_phrase = f"{last_word} ..."  # Bot chỉ nối đơn giản
    
    game.used_phrases[bot_phrase.lower()] = 1
    game.current_phrase = bot_phrase
    game.next_player()
    
    await context.bot.send_message(
        chat_id=context._chat_id,
        text=f"🤖 Bot nối: '{bot_phrase}'"
    )
    
    # Chuyển lượt tiếp theo
    if len(game.players) == 1:
        await end_game(context)
        return
    
    next_player = game.players[game.current_player_index]
    
    if next_player["id"] == 0:  # Bot tiếp tục chơi
        await asyncio.sleep(1)
        await bot_turn(context)
        return
    
    mention = f"<a href='tg://user?id={next_player['id']}'>@{next_player['name']}</a>"
    await context.bot.send_message(
        chat_id=context._chat_id,
        text=f"👤 Lượt tiếp: {mention}\n"
             f"🔗 Nối từ: '{game.current_phrase.split()[-1]}'",
        parse_mode="HTML"
    )
    await start_turn_timer(context)

async def eliminate_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Loại người chơi"""
    user = update.effective_user
    game.remove_player(user.id)
    
    await update.message.reply_text(
        f"❌ {user.full_name} đã bị loại!\n"
        f"👥 Còn lại: {len(game.players)} người"
    )
    
    if len(game.players) == 1:
        await end_game(context)
    else:
        await begin_game(update, context)

async def end_game(context: ContextTypes.DEFAULT_TYPE):
    """Kết thúc game"""
    if not game.players:
        await context.bot.send_message(
            chat_id=context._chat_id,
            text="🎉 Game kết thúc!"
        )
        game.reset()
        return
    
    winner = game.players[0]
    game.winner_counts[winner["id"]] = game.winner_counts.get(winner["id"], 0) + 1
    
    if winner["id"] == 0:
        result_text = "🏆 Bot chiến thắng! 🤖"
    else:
        mention = f"<a href='tg://user?id={winner['id']}'>@{winner['name']}</a>"
        win_count = game.winner_counts[winner["id"]]
        result_text = f"🏆 {mention} chiến thắng!\n⭐ Tổng thắng: {win_count} lần"
    
    await context.bot.send_message(
        chat_id=context._chat_id,
        text=result_text,
        parse_mode="HTML"
    )
    game.reset()

# ===== QUẢN LÝ THỜI GIAN =====
async def start_turn_timer(context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu đếm ngược 59 giây"""
    if game.turn_timeout_task:
        game.turn_timeout_task.cancel()
    
    game.turn_timeout_task = asyncio.create_task(turn_timer(context))

async def turn_timer(context: ContextTypes.DEFAULT_TYPE):
    """Xử lý hết giờ"""
    try:
        await asyncio.sleep(59)
        
        if not game.in_game or not game.players:
            return
        
        current_player = game.players[game.current_player_index]
        
        if current_player["id"] == 0:  # Bot không bị timeout
            return
        
        game.remove_player(current_player["id"])
        mention = f"<a href='tg://user?id={current_player['id']}'>@{current_player['name']}</a>"
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"⏰ {mention} hết thời gian và bị loại!",
            parse_mode="HTML"
        )
        
        if len(game.players) == 1:
            await end_game(context)
        else:
            await begin_game(None, context)
            
    except asyncio.CancelledError:
        pass

# ===== KHỞI CHẠY BOT =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Đăng ký handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("botplay", bot_play))
    app.add_handler(CommandHandler("begin", begin_game))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
