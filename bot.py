import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from PIL import Image
import pytesseract

# ===== CONFIG =====
TOKEN = os.getenv("BOT_TOKEN")
FILE_PATH = "files/current.html"

logging.basicConfig(level=logging.INFO)

# ===== CHECK LOGIC =====
def is_subscribed(text: str) -> bool:
    text = text.lower()
    return "firecube" in text and "подпис" in text

# ===== COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправь скриншот, где видно подписку на FireCube"
    )

# ===== PHOTO HANDLER =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        path = "temp.jpg"
        await file.download_to_drive(path)

        image = Image.open(path)
        text = pytesseract.image_to_string(image)

        logging.info(f"OCR TEXT: {text}")

        if is_subscribed(text):
            with open(FILE_PATH, "rb") as f:
                await update.message.reply_document(f)
        else:
            await update.message.reply_text("❌ Подписка не найдена")

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Ошибка обработки скрина")

# ===== MAIN =====
def main():
    if not TOKEN:
        print("BOT_TOKEN not set")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
