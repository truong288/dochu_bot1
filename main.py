from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from stay_alive import keep_alive
import asyncio
import re
import random


keep_alive()

# Game state
players = []
current_phrase = ""
used_phrases = {}
current_player_index = 0
in_game = False
waiting_for_phrase = False
turn_timeout_task = None
bot_playing = False

# Bad words 
BAD_WORDS = {"đần", "bần", "ngu", "ngốc", "bò", "dốt", "nát", "chó", "địt", "mẹ", "mày", "má"}

def reset_game():
    global players, current_phrase, used_phrases, current_player_index, in_game, waiting_for_phrase, turn_timeout_task, bot_playing
    players = []
    current_phrase = ""
    used_phrases = {}
    current_player_index = 0
    in_game = False
    waiting_for_phrase = False
    bot_playing = False
    if turn_timeout_task:
        turn_timeout_task.cancel()
        turn_timeout_task = None


def contains_bad_word(text):
    return any(word in text.lower() for word in BAD_WORDS)


def is_vietnamese(text):
    vietnamese_chars = r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
    return bool(re.search(vietnamese_chars, text))


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_game()
    global in_game
    in_game = True

    await update.message.reply_text("🎮 Trò chơi bắt đầu!\n"
                                   "👉 Gõ /join để tham gia.\n"
                                   "👉 Gõ /begin để bắt đầu chơi.\n"
                                   "👉 Gõ /botplay để chơi với bot")


async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players
    user = update.effective_user
    if user.id not in players:
        players.append(user.id)
        await update.message.reply_text(
            f"✅ {user.first_name} đã tham gia... (Tổng {len(players)})")
    else:
        await update.message.reply_text("⚠️ Bạn đã tham gia rồi!")


async def bot_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_playing
    bot_playing = True
    await start_game(update, context)
    await join_game(update, context)
    players.append(0)  # 0 represents bot
    await update.message.reply_text("🤖 Bot đã tham gia! Gõ /begin để bắt đầu.")


async def begin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_player_index, waiting_for_phrase
    if len(players) < 2:
        await update.message.reply_text("❗ Cần ít nhất 2 người chơi để bắt đầu.")
        return

    waiting_for_phrase = True
    user_id = players[current_player_index]
    
    if user_id == 0:  # Bot's turn
        await bot_turn(context)
        return
    
    chat = await context.bot.get_chat(user_id)
    mention = f"<a href='tg://user?id={user_id}'>@{chat.username or chat.first_name}</a>"

    await update.message.reply_text(
        f"✏️ {mention}, hãy nhập cụm từ đầu tiên để bắt đầu trò chơi!",
        parse_mode="HTML")
    await start_turn_timer(context)


async def bot_turn(context):
    global current_phrase, current_player_index, used_phrases
    
    if not current_phrase:  # First turn
        bot_phrase = random.choice(SAMPLE_PHRASES)
        current_phrase = bot_phrase
        used_phrases[bot_phrase] = 1
        current_player_index = (current_player_index + 1) % len(players)
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"🤖 Bot chọn: '{bot_phrase}'"
        )
        
        if players[current_player_index] == 0:  # Next player is also bot
            await asyncio.sleep(2)
            await bot_turn(context)
        else:
            next_id = players[current_player_index]
            next_chat = await context.bot.get_chat(next_id)
            mention = f"<a href='tg://user?id={next_id}'>@{next_chat.username or next_chat.first_name}</a>"
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=f"✅ Từ bắt đầu là: '{bot_phrase}'. {mention}, hãy nối với từ '{bot_phrase.split()[-1]}'",
                parse_mode="HTML")
            await start_turn_timer(context)
    else:
        last_word = current_phrase.split()[-1]
        possible_phrases = [phrase for phrase in SAMPLE_PHRASES 
                          if phrase.startswith(last_word) and phrase not in used_phrases]
        
        if possible_phrases:
            bot_phrase = random.choice(possible_phrases)
        else:
            bot_phrase = last_word + " ... 🤖 Bot bí!"
        
        used_phrases[bot_phrase] = 1
        current_phrase = bot_phrase
        current_player_index = (current_player_index + 1) % len(players)
        
        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"🤖 Bot nối: '{bot_phrase}'"
        )
        
        if len(players) == 1:
            await context.bot.send_message(
                chat_id=context._chat_id,
                text="🏆 Bot chiến thắng! 🤖🎉")
            reset_game()
            return
            
        if players[current_player_index] == 0:  # Next player is also bot
            await asyncio.sleep(2)
            await bot_turn(context)
        else:
            next_id = players[current_player_index]
            next_chat = await context.bot.get_chat(next_id)
            mention = f"<a href='tg://user?id={next_id}'>@{next_chat.username or next_chat.first_name}</a>"
            await context.bot.send_message(
                chat_id=context._chat_id,
                text=f"✅ Hợp lệ! Nối tiếp từ: '{bot_phrase.split()[-1]}'. Tới lượt bạn {mention}",
                parse_mode="HTML")
            await start_turn_timer(context)


async def play_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not in_game:
        return

    user = update.effective_user
    text = update.message.text.strip().lower()

    if user.id != players[current_player_index]:
        return

   # Kiểm tra từ cấm
    if contains_bad_word(text):
        await update.message.reply_text("❌ Từ cấm! Bị loại!")
        await eliminate_player(update)
        return
    
    # Kiểm tra tiếng Việt
    if not is_vietnamese(text):
        await update.message.reply_text("❌ Chỉ dùng tiếng Việt!")
        await eliminate_player(update)
        return
    
    # Kiểm tra 2 từ
    if len(text.split()) != 2:
        await update.message.reply_text("❌ Phải nhập 2 từ!")
        return

    if waiting_for_phrase:
        current_phrase = text
        used_phrases[text] = 1
        waiting_for_phrase = False
        current_player_index = (current_player_index + 1) % len(players)

        if players[current_player_index] == 0:  # Bot's turn next
            await bot_turn(context)
            return
            
        next_id = players[current_player_index]
        next_chat = await context.bot.get_chat(next_id)
        mention = f"<a href='tg://user?id={next_id}'>@{next_chat.username or next_chat.first_name}</a>"

        await update.message.reply_text(
            f"✅ Từ bắt đầu là: '{text}'. {mention}, hãy nối với từ '{text.split()[-1]}'",
            parse_mode="HTML")
        await start_turn_timer(context)
        return

    if text.split()[0] != current_phrase.split()[-1]:
        await eliminate_player(update, context, reason="Không đúng từ nối")
        return

    if used_phrases.get(text, 0) >= 1:
        await eliminate_player(update, context, reason="Cụm từ đã bị sử dụng")
        return

    used_phrases[text] = 1
    current_phrase = text
    current_player_index = (current_player_index + 1) % len(players)

    if len(players) == 1:
        winner_id = players[0]
        if winner_id == 0:
            await update.message.reply_text("🏆 Bot chiến thắng! 🤖🎉")
        else:
            chat = await context.bot.get_chat(winner_id)
            mention = f"<a href='tg://user?id={winner_id}'>@{chat.username or chat.first_name}</a>"
            await update.message.reply_text(f"🏆 {mention} Vô Địch Nối CHỮ!🏆🏆",
                                          parse_mode="HTML")
        reset_game()
        return

    if players[current_player_index] == 0:  # Bot's turn next
        await bot_turn(context)
        return
        
    next_id = players[current_player_index]
    next_chat = await context.bot.get_chat(next_id)
    next_mention = f"<a href='tg://user?id={next_id}'>@{next_chat.username or next_chat.first_name}</a>"

    await update.message.reply_text(
        f"✅ Hợp lệ! Nối tiếp từ: '{text.split()[-1]}'. Tới lượt bạn {next_mention}",
        parse_mode="HTML")
    await start_turn_timer(context)


async def eliminate_player(update, context, reason):
    global players, current_player_index
    user = update.effective_user
    await update.message.reply_text(
        f"❌ {user.first_name} bị loại! Lý do: {reason}")
    players.remove(user.id)
    if current_player_index >= len(players):
        current_player_index = 0

    if len(players) == 1:
        winner_id = players[0]
        if winner_id == 0:
            await update.message.reply_text("🏆 Bot chiến thắng! 🤖🎉")
        else:
            chat = await context.bot.get_chat(winner_id)
            mention = f"<a href='tg://user?id={winner_id}'>@{chat.username or chat.first_name}</a>"
            await update.message.reply_text(f"🏆 {mention} Vô Địch Nối CHỮ!🏆🏆",
                                          parse_mode="HTML")
        reset_game()
    else:
        await update.message.reply_text(
            f"Hiện còn lại {len(players)} người chơi.")
        await begin_game(update, context)


async def start_turn_timer(context):
    global turn_timeout_task
    if turn_timeout_task:
        turn_timeout_task.cancel()
    turn_timeout_task = asyncio.create_task(turn_timer(context))


async def turn_timer(context):
    global players, current_player_index
    try:
        await asyncio.sleep(59)
        user_id = players[current_player_index]
        
        if user_id == 0:  # Bot's turn - shouldn't timeout
            return
            
        chat = await context.bot.get_chat(user_id)
        mention = f"<a href='tg://user?id={user_id}'>@{chat.username or chat.first_name}</a>"

        await context.bot.send_message(
            chat_id=context._chat_id,
            text=f"⏰ {mention} hết thời gian và bị loại!",
            parse_mode="HTML")
        players.remove(user_id)

        if len(players) == 1:
            winner_id = players[0]
            if winner_id == 0:
                await context.bot.send_message(
                    chat_id=context._chat_id,
                    text="🏆 Bot chiến thắng! 🤖🎉")
            else:
                winner_chat = await context.bot.get_chat(winner_id)
                mention = f"<a href='tg://user?id={winner_id}'>@{winner_chat.username or winner_chat.first_name}</a>"
                await context.bot.send_message(
                    chat_id=context._chat_id,
                    text=f"🏆 {mention} Vô Địch Nối CHỮ!🏆🏆",
                    parse_mode="HTML")
            reset_game()
            return

        if current_player_index >= len(players):
            current_player_index = 0

        await start_turn_timer(context)

    except asyncio.CancelledError:
        pass


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/startgame - Bắt đầu trò chơi\n"
        "/join - Tham gia\n"
        "/botplay - Chơi với bot\n"
        "/begin - Bắt đầu sau khi đủ người\n"
        "/help - Hướng dẫn\n\n"
        "📌 Luật chơi:\n"
        "- Mỗi người nhập cụm từ 2 từ\n"
        "- Từ đầu phải nối với từ cuối của người trước\n"
        "- Không dùng từ cấm hoặc không phải tiếng Việt\n"
        "- Mỗi lượt có 59 giây"
    )


if __name__ == '__main__':
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("botplay", bot_play))
    app.add_handler(CommandHandler("begin", begin_game))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play_word))

    print("Bot is running...")
    app.run_polling()
