import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, 
    CommandHandler, 
    MessageHandler, 
    Filters, 
    CallbackContext,
    CallbackQueryHandler
)
from collections import defaultdict
from datetime import datetime, timedelta
import random
import re

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Từ điển từ cấm
BANNED_WORDS = {'đần', 'bần', 'ngu', 'ngôc', 'bò', 'dốt', 'nát', 'địt', 'đụ', 'lồn', 'cặc', 'đĩ', 'cứt'}

class WordChainGame:
    def __init__(self):
        self.reset_game()
        
    def reset_game(self):
        self.players = set()
        self.current_player = None
        self.starter_player = None
        self.used_words = set()
        self.last_word = None
        self.last_time = None
        self.game_started = False
        self.join_phase = True
        self.turn_timeout = 59  # 59 giây mỗi lượt
        
    def add_player(self, player_id, player_name):
        self.players.add((player_id, player_name))
        if len(self.players) == 1:
            self.starter_player = (player_id, player_name)
            self.current_player = (player_id, player_name)
            
    def start_game(self):
        if len(self.players) >= 2:
            self.game_started = True
            self.join_phase = False
            return True
        return False
        
    def is_valid_word(self, word):
        # Kiểm tra từ có 2 từ trở lên và không chứa từ cấm
        if len(word.split()) < 2:
            return False
            
        word_lower = word.lower()
        for banned in BANNED_WORDS:
            if banned in word_lower:
                return False
                
        return True
        
    def is_valid_chain(self, new_word):
        if not self.last_word:
            return True
            
        last_char = self.last_word.split()[-1][-1].lower()
        first_char = new_word.split()[0][0].lower()
        
        return last_char == first_char
        
    def play_turn(self, player_id, word):
        now = datetime.now()
        
        # Kiểm tra đến lượt
        if player_id != self.current_player[0]:
            return False, "Không phải lượt của bạn!"
            
        # Kiểm tra thời gian
        if self.last_time and (now - self.last_time).seconds > self.turn_timeout:
            return False, "Đã hết thời gian cho lượt này!"
            
        # Kiểm tra từ hợp lệ
        if not self.is_valid_word(word):
            return False, "Từ không hợp lệ (phải có 2 từ trở lên hoặc chứa từ cấm)"
            
        # Kiểm tra từ đã dùng
        if word.lower() in self.used_words:
            return False, "Từ này đã được sử dụng trước đó!"
            
        # Kiểm tra nối từ
        if not self.is_valid_chain(word):
            return False, "Không nối được từ! Phải bắt đầu bằng chữ cái kết thúc của từ trước"
            
        # Cập nhật trạng thái game
        self.used_words.add(word.lower())
        self.last_word = word
        self.last_time = now
        
        # Chuyển lượt
        players_list = list(self.players)
        current_index = players_list.index(self.current_player)
        next_index = (current_index + 1) % len(players_list)
        self.current_player = players_list[next_index]
        
        return True, None

# Khởi tạo game
game = WordChainGame()

# Hàm xử lý lệnh
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Chào mừng đến với trò chơi Nối từ!\n\n"
        "Các lệnh:\n"
        "/startgame - Bắt đầu trò chơi\n"
        "/join - Tham gia\n"
        "/reset - Đặt lại trò chơi\n"
        "/help - Xem hướng dẫn\n"
        "/begin - Bắt đầu sau khi đủ người chơi\n"
    )

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "📖 Hướng dẫn chơi:\n\n"
        "1. Người đầu tiên dùng /join sẽ là người đặt câu hỏi đầu tiên\n"
        "2. Mỗi lượt chơi có 59 giây\n"
        "3. Không được lặp lại từ đã dùng\n"
        "4. Phải nối từ hợp lệ (ví dụ: 'bầu trời' -> 'trời nắng')\n"
        "5. Từ phải có ít nhất 2 từ và không chứa từ ngữ tiêu cực\n\n"
        "Các lệnh:\n"
        "/join - Tham gia trò chơi\n"
        "/startgame - Bắt đầu trò chơi (chủ phòng)\n"
        "/begin - Bắt đầu sau khi đủ người\n"
        "/reset - Đặt lại trò chơi\n"
    )

def join(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if game.join_phase:
        game.add_player(user.id, user.first_name)
        update.message.reply_text(f"{user.first_name} đã tham gia trò chơi!")
        
        if game.starter_player and game.starter_player[0] == user.id:
            update.message.reply_text(
                f"Bạn là người bắt đầu trò chơi! Hãy gửi từ đầu tiên sau khi trò chơi bắt đầu."
            )
    else:
        update.message.reply_text("Hiện không trong giai đoạn tham gia. Dùng /reset để tạo game mới.")

def startgame(update: Update, context: CallbackContext) -> None:
    if len(game.players) >= 1:
        update.message.reply_text(
            "Trò chơi đã sẵn sàng! Dùng /begin để bắt đầu khi đã đủ người chơi.\n"
            f"Hiện có {len(game.players)} người tham gia."
        )
    else:
        update.message.reply_text("Chưa có ai tham gia. Dùng /join để tham gia trò chơi.")

def begin(update: Update, context: CallbackContext) -> None:
    if game.start_game():
        starter_name = game.starter_player[1]
        update.message.reply_text(
            f"Trò chơi bắt đầu! {starter_name} là người bắt đầu.\n"
            f"{starter_name}, hãy gửi từ đầu tiên (gồm 2 từ trở lên)."
        )
    else:
        update.message.reply_text("Cần ít nhất 2 người chơi để bắt đầu!")

def reset(update: Update, context: CallbackContext) -> None:
    game.reset_game()
    update.message.reply_text("Trò chơi đã được đặt lại. Dùng /join để tham gia.")

def handle_message(update: Update, context: CallbackContext) -> None:
    if not game.game_started:
        return
        
    user = update.effective_user
    word = update.message.text.strip()
    
    success, error = game.play_turn(user.id, word)
    
    if success:
        next_player = game.current_player[1]
        update.message.reply_text(
            f"✅ Từ '{word}' được chấp nhận!\n"
            f"⏳ Thời gian còn lại: {game.turn_timeout} giây\n"
            f"🎮 Đến lượt: {next_player}"
        )
    elif error:
        update.message.reply_text(f"❌ {error}")

def main() -> None:
    # Lấy token từ biến môi trường
    TOKEN = os.getenv('7995385268:AAEx4uelfTCYtzkze0vZ4G4eDaau_EfYnjw')
    if not TOKEN:
        raise ValueError("Vui lòng đặt biến môi trường TELEGRAM_TOKEN")
    
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Đăng ký các lệnh
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("join", join))
    dispatcher.add_handler(CommandHandler("startgame", startgame))
    dispatcher.add_handler(CommandHandler("begin", begin))
    dispatcher.add_handler(CommandHandler("reset", reset))
    
    # Xử lý tin nhắn thường
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Bắt đầu bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
