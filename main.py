import re
import asyncio
import random
from collections import defaultdict
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

# ===== CẤU HÌNH =====
BOT_TOKEN = "7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw"
DICTIONARY_API = "https://api.tudien.com/check"  # (Có thể bỏ qua nếu không có)

# ===== LỚP QUẢN LÝ GAME =====
class GameManager:
    def __init__(self):
        self.reset()
        self.learned_pairs = defaultdict(list)  # Lưu các cặp từ học được từ người chơi
        self.common_prefixes = ["trời", "mưa", "nắng", "hoa", "cây", "nhà", "sông", "núi"]
        self.common_suffixes = ["đẹp", "cao", "lớn", "nhỏ", "xanh", "vàng", "to", "nhẹ"]

    def reset(self):
        self.players: List[Dict] = []
        self.current_phrase: str = ""
        self.used_phrases: Dict[str, int] = {}
        self.current_player_index: int = 0
        self.in_game: bool = False
        self.waiting_for_phrase: bool = False
        self.turn_timeout_task: Optional[asyncio.Task] = None
        self.bot_playing: bool = False
        self.winner_counts: Dict[int, int] = {}

    def add_player(self, user_id: int, username: str):
        if user_id not in [p["id"] for p in self.players]:
            self.players.append({"id": user_id, "name": username})

    def next_player(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        return self.players[self.current_player_index]

    def remove_player(self, user_id: int) -> int:
        self.players = [p for p in self.players if p["id"] != user_id]
        if self.current_player_index >= len(self.players):
            self.current_player_index = 0
        return len(self.players)

    def learn_new_pair(self, last_word: str, new_word: str):
        """Học cặp từ mới từ người chơi"""
        if new_word not in self.learned_pairs[last_word]:
            self.learned_pairs[last_word].append(new_word)

    def generate_bot_phrase(self, last_word: str) -> str:
        """Tạo cụm từ mới cho bot một cách thông minh"""
        # Ưu tiên dùng các cặp đã học được
        if last_word in self.learned_pairs and self.learned_pairs[last_word]:
            learned_options = [phrase for phrase in self.learned_pairs[last_word] 
                             if f"{last_word} {phrase}".lower() not in self.used_phrases]
            if learned_options:
                return f"{last_word} {random.choice(learned_options)}"

        # Tạo các lựa chọn đa dạng
        patterns = [
            # Mẫu 1: Tính từ
            f"{last_word} {random.choice(self.common_suffixes)}",
            # Mẫu 2: Kết hợp với từ tự nhiên
            f"{last_word} {random.choice(['và', 'cùng', 'với'])} {random.choice(self.common_prefixes)}",
            # Mẫu 3: Đảo vị trí
            f"{random.choice(self.common_prefixes)} {last_word}",
            # Mẫu 4: Giới từ + danh từ
            f"{last_word} {random.choice(['trên', 'dưới', 'trong', 'ngoài'])} {random.choice(self.common_prefixes)}"
        ]

        # Tạo 5 ứng viên và chọn cái chưa dùng
        candidates = [random.choice(patterns) for _ in range(5)]
        unused = [phrase for phrase in candidates if phrase.lower() not in self.used_phrases]

        return random.choice(unused) if unused else f"{last_word} {random.choice(self.common_suffixes)}"

game = GameManager()

# ===== TIỆN ÍCH KIỂM TRA =====
def contains_bad_word(text: str) -> bool:
    BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}
    text_lower = text.lower()
    return any(bad_word in text_lower for bad_word in BAD_WORDS)

def is_vietnamese(text: str) -> bool:
    vietnamese_pattern = re.compile(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        re.IGNORECASE
    )
    return bool(vietnamese_pattern.search(text))

async def validate_phrase(phrase: str) -> Tuple[bool, Optional[str]]:
    words = phrase.strip().split()
    
    if len(words) != 2:
        return False, "Phải nhập chính xác 2 từ"
    
    if contains_bad_word(phrase):
        return False, "Chứa từ cấm"
    
    if not is_vietnamese(phrase):
        return False, "Phải dùng tiếng Việt"
    
    return True, None

# ===== HANDLER LỆNH =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Game Nối Chữ - Luật chơi:\n"
        "1. Nhập cụm từ 2 từ\n2. Nối từ cuối của người trước\n"
        "3. Không dùng từ cấm\n4. Thời gian mỗi lượt: 59 giây\n\n"
        "📝 Lệnh:\n/startgame - Bắt đầu\n/join - Tham gia\n"
        "/botplay - Chơi với bot\n/begin - Bắt đầu khi đủ người"
    )

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game.reset()
    game.in_game = True
    await update.message.reply_text("🎉 Game đã khởi tạo! Gõ /join để tham gia")

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game.add_player(user.id, user.full_name)
    await update.message.reply_text(f"✅ {user.full_name} đã tham gia! (Tổng: {len(game.players)})")

async def bot_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game.bot_playing = True
    game.add_player(0, "Bot 🤖")
    await update.message.reply_text("🤖 Bot đã tham gia!")

async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(game.players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi!")
        return
    
    game.waiting_for_phrase = True
    current_player = game.players[game.current_player_index]
    
    if current_player["id"] == 0:
        await bot_turn(context)
    else:
        mention = f"<a href='tg://user?id={current_player['id']}'>@{current_player['name']}</a>"
        await update.message.reply_text(
            f"✏️ {mention}, nhập cụm từ đầu tiên! (2 từ)",
            parse_mode="HTML"
        )
        await start_turn_timer(context)

# ===== XỬ LÝ GAME CHÍNH =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game.in_game:
        return
    
    user = update.effective_user
    current_player = game.players[game.current_player_index] if game.players else None
    
    if not current_player or user.id != current_player["id"]:
        return
    
    text = update.message.text.strip()
    is_valid, error = await validate_phrase(text)
    
    if not is_valid:
        await update.message.reply_text(f"❌ Lỗi: {error}")
        remaining = game.remove_player(user.id)
        await handle_player_elimination(remaining, context)
        return
    
    if game.waiting_for_phrase:
        game.current_phrase = text
        game.used_phrases[text.lower()] = 1
        game.waiting_for_phrase = False
    else:
        if text.lower().split()[0] != game.current_phrase.split()[-1].lower():
            await update.message.reply_text("❌ Không đúng từ nối!")
            remaining = game.remove_player(user.id)
            await handle_player_elimination(remaining, context)
            return
        
        if text.lower() in game.used_phrases:
            await update.message.reply_text("❌ Cụm từ đã được dùng!")
            remaining = game.remove_player(user.id)
            await handle_player_elimination(remaining, context)
            return
        
        # Học cặp từ mới từ người chơi
        last_word = game.current_phrase.split()[-1].lower()
        current_word = text.split()[0].lower()
        game.learn_new_pair(last_word, current_word)
        
        game.used_phrases[text.lower()] = 1
        game.current_phrase = text
    
    game.next_player()
    
    if len(game.players) == 1:
        await end_game(context)
    else:
        await continue_game(context)

async def bot_turn(context: ContextTypes.DEFAULT_TYPE):
    if not game.current_phrase:
        # Các cụm từ mở đầu đa dạng
        starters = ["bầu trời", "mặt trời", "hoa lá", "chim muông", "sông nước", 
                   "núi non", "biển cả", "trăng sao", "mây gió", "cây cối"]
        bot_phrase = random.choice(starters)
    else:
        last_word = game.current_phrase.split()[-1].lower()
        bot_phrase = game.generate_bot_phrase(last_word)
    
        # Đảm bảo không trùng lặp
        attempts = 0
        while bot_phrase.lower() in game.used_phrases and attempts < 5:
            bot_phrase = game.generate_bot_phrase(last_word)
            attempts += 1
        
        if attempts == 5:
            bot_phrase = f"{last_word} {random.choice(game.common_suffixes)}"

    game.used_phrases[bot_phrase.lower()] = 1
    game.current_phrase = bot_phrase
    game.next_player()
    
    await context.bot.send_message(
        chat_id=context._chat_id,
        text=f"🤖 Bot đã nối từ\n"
             f"👉 Cụm từ mới: 『{bot_phrase}』\n"
             f"👉 Từ cần nối tiếp: 『{bot_phrase.split()[-1]}』",
        parse_mode="HTML"
    )
    
    if len(game.players) == 1:
        await end_game(context)
    else:
        await continue_game(context)

async def handle_player_elimination(remaining: int, context: ContextTypes.DEFAULT_TYPE):
    if remaining == 1:
        await end_game(context)
    else:
        last_word = game.current_phrase.split()[-1] if game.current_phrase else ""
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"👤 Số người chơi còn lại: {remaining}\n"
                 f"👉 Từ cần nối tiếp: 『{last_word}』",
            parse_mode="HTML"
        )
        await continue_game(context)

async def continue_game(context: ContextTypes.DEFAULT_TYPE):
    current_player = game.players[game.current_player_index]
    last_word = game.current_phrase.split()[-1] if game.current_phrase else ""
    
    if current_player["id"] == 0:
        await bot_turn(context)
    else:
        mention = f"<a href='tg://user?id={current_player['id']}'>@{current_player['name']}</a>"
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"🔄 Lượt chơi tiếp theo\n"
                 f"👉 Từ cần nối: 『{last_word}』\n"
                 f"👤 Người chơi: {mention}\n"
                 f"⏳ Thời gian: 59 giây",
            parse_mode="HTML"
        )
        await start_turn_timer(context)

async def end_game(context: ContextTypes.DEFAULT_TYPE):
    if not game.players:
        await context.bot.send_message(chat_id=context._chat_id, text="🎉 Game kết thúc!")
    else:
        winner = game.players[0]
        game.winner_counts[winner["id"]] = game.winner_counts.get(winner["id"], 0) + 1
        
        if winner["id"] == 0:
            result_text = "🏆 Bot chiến thắng! 🤖"
        else:
            mention = f"<a href='tg://user?id={winner['id']}'>@{winner['name']}</a>"
            result_text = f"🏆 {mention} thắng! (Tổng: {game.winner_counts[winner['id']]} lần)"
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=result_text,
            parse_mode="HTML"
        )
    game.reset()

# ===== QUẢN LÝ THỜI GIAN =====
async def start_turn_timer(context: ContextTypes.DEFAULT_TYPE):
    if game.turn_timeout_task:
        game.turn_timeout_task.cancel()
    game.turn_timeout_task = asyncio.create_task(turn_timer(context))

async def turn_timer(context: ContextTypes.DEFAULT_TYPE):
    try:
        await asyncio.sleep(59)
        
        if not game.in_game or not game.players:
            return
        
        current_player = game.players[game.current_player_index]
        if current_player["id"] == 0:
            return
        
        remaining = game.remove_player(current_player["id"])
        mention = f"<a href='tg://user?id={current_player['id']}'>@{current_player['name']}</a>"
        last_word = game.current_phrase.split()[-1] if game.current_phrase else ""
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"⏰ {mention} hết giờ và bị loại!\n"
                 f"👉 Từ cần nối tiếp: 『{last_word}』",
            parse_mode="HTML"
        )
        
        if remaining == 1:
            await end_game(context)
        else:
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=f"👥 Còn lại: {remaining} người"
            )
            await continue_game(context)
    except asyncio.CancelledError:
        pass

# ===== KHỞI CHẠY =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("botplay", bot_play))
    app.add_handler(CommandHandler("begin", begin_game))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot đang chạy...")
    app.run
