import os
import sys
import random
import requests
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, Poll
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator

# Thiết lập UTF-8 để không bị lỗi ký tự Unicode trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database as db
import excel_exporter as exporter

# Web server mini giúp Render nhận diện bot đang sống (không bị lỗi port)
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")
    def log_message(self, format, *args):
        pass

def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

BOT_TOKEN = "8293161016:AAGPDbP0zB4rK5WpQ6ewYoPELWrKGtInb4k"
user_units = {}

def lookup_dictionary(word):
    word_type = "n"
    try:
        res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=4)
        if res.status_code == 200:
            data = res.json()
            meanings = data[0].get("meanings", [])
            if meanings:
                word_type = meanings[0].get("partOfSpeech", "n")
    except Exception:
        pass

    try:
        vietnamese = GoogleTranslator(source="en", target="vi").translate(word)
    except Exception:
        vietnamese = "Chưa rõ nghĩa"

    return word_type, vietnamese

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        ["📖 Danh sách từ", "📝 Xuất file Excel"],
        ["🎯 Trắc nghiệm Quiz", "✍️ Ôn tập ngẫu nhiên"],
        ["📚 Đổi Unit"]
    ]
    reply_markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    welcome_text = (
        "👋 Chào mừng bạn đến với **Bot Học Từ Vựng Tiếng Anh**!\n\n"
        "✨ **Cách sử dụng:**\n"
        "1. **Tự động tra nghĩa:** Gõ từ tiếng Anh gửi vào đây (VD: `curiosity` hoặc `nuclear family`).\n"
        "2. **Tự định nghĩa:** `từ | loại từ | nghĩa`\n"
        "   (VD: `upset someone | v.phr | làm ai đó buồn lòng`)\n\n"
        "📊 Bấm **📝 Xuất file Excel** để nhận file bài tập tự kiểm tra đúng/sai chuẩn mẫu!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def set_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.replace("📚 Đổi Unit", "").replace("/unit", "").strip()
    if not text:
        await update.message.reply_text("Vui lòng nhập tên Unit, ví dụ: `/unit Unit 2`", parse_mode="Markdown")
        return
    user_units[user_id] = text
    await update.message.reply_text(f"✅ Đã chuyển sang: *{text}*", parse_mode="Markdown")

async def export_excel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_unit = user_units.get(user_id, "Unit 2")
    words = db.get_words(user_id, current_unit)
    
    if not words:
        await update.message.reply_text(f"⚠️ *{current_unit}* chưa có từ vựng nào! Bạn hãy gửi vài từ tiếng Anh vào đây trước nhé.", parse_mode="Markdown")
        return

    filename = f"Bai_tap_Tu_vung_{current_unit.replace(' ', '_')}.xlsx"
    exporter.export_vocab_excel(words, unit_name=current_unit, filename=filename)
    
    await update.message.reply_document(
        document=open(filename, "rb"),
        filename=filename,
        caption=f"📊 File bài tập tự kiểm tra cho *{current_unit}* của bạn đây!\n"
                f"💡 Mở file bằng Excel, gõ từ vào Cột D. Cột E sẽ tự động hiện **ĐÚNG ✓** hoặc **SAI ✗** kèm màu.",
        parse_mode="Markdown"
    )

async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_unit = user_units.get(user_id, None)
    words = db.get_words(user_id, current_unit)
    
    if len(words) < 4:
        await update.message.reply_text("⚠️ Bạn cần lưu ít nhất 4 từ vựng để tạo bài Quiz trắc nghiệm!")
        return

    quiz_sample = random.sample(words, 4)
    target = quiz_sample[0]
    _, target_word, _, target_vi, _ = target

    options = [w[1] for w in quiz_sample]
    random.shuffle(options)
    correct_id = options.index(target_word)

    await update.message.reply_poll(
        question=f"Từ tiếng Anh nào có nghĩa là: '{target_vi}'?",
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_id,
        is_anonymous=False,
        explanation=f"Đáp án chính xác: {target_word} ({target_vi})"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    current_unit = user_units.get(user_id, "Unit 2")

    if text == "📝 Xuất file Excel":
        return await export_excel_handler(update, context)
    elif text == "🎯 Trắc nghiệm Quiz":
        return await quiz_handler(update, context)
    elif text == "📖 Danh sách từ":
        words = db.get_words(user_id, current_unit)
        if not words:
            return await update.message.reply_text(f"Hiện tại *{current_unit}* chưa có từ nào.", parse_mode="Markdown")
        msg = f"📚 **TỪ VỰNG TRONG {current_unit.upper()}:**\n\n"
        for idx, (_, w, t, v, _) in enumerate(words, 1):
            msg += f"{idx}. *{w}* (`{t}`): {v}\n"
        return await update.message.reply_text(msg, parse_mode="Markdown")
    elif text in ["📚 Đổi Unit", "✍️ Ôn tập ngẫu nhiên"]:
        return await update.message.reply_text("Gõ `/unit Tên_Unit` (VD: `/unit Unit 2`) để chuyển Unit.", parse_mode="Markdown")

    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        word = parts[0]
        word_type = parts[1] if len(parts) > 1 else "n"
        vietnamese = parts[2] if len(parts) > 2 else ""
    else:
        word = text
        word_type, vietnamese = lookup_dictionary(word)

    db.add_word(user_id, word, word_type, vietnamese, current_unit)
    
    reply = (
        f"✅ **Đã lưu từ thành công!**\n\n"
        f"• Từ: **{word}**\n"
        f"• Loại từ: `{word_type}`\n"
        f"• Nghĩa tiếng Việt: {vietnamese}\n"
        f"• Thuộc: _{current_unit}_"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

def main():
    db.init_db()
    
    # Khởi động server web phụ để Render nhận diện port
    threading.Thread(target=start_dummy_server, daemon=True).start()

    # Thiết lập event loop an toàn cho mọi phiên bản Python (kể cả Python 3.14 trên Render)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("export", export_excel_handler))
    app.add_handler(CommandHandler("quiz", quiz_handler))
    app.add_handler(CommandHandler("unit", set_unit))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("[INFO] Bot MyVocabMasterBot is now running successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()
