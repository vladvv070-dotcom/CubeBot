import os
import re
import uuid
from PIL import Image
import pytesseract

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ===== НАСТРОЙКИ =====
TOKEN = os.getenv("BOT_TOKEN")
FILE_PATH = "files/current.html"

# OCR путь для Render/Linux
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"


# ===== ПОЛУЧИТЬ ВЕРСИЮ ИЗ HTML =====
def get_timer_version() -> str:
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'class="version-display"[^>]*>CubeTimer\s*([\d.]+)<', content)
        if match:
            return match.group(1)
        return "неизвестна"
    except FileNotFoundError:
        return "файл не найден"


# ===== КЛАВИАТУРА =====
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Какая актуальная версия?", callback_data="version")]
    ])


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет!\n\n"
        "1. Подпишись на YouTube канал FireCube\n"
        "2. Отправь скриншот, где видно:\n"
        "- FireCube\n"
        "- Вы подписаны\n\n"
        "После проверки бот выдаст файл.",
        reply_markup=main_keyboard()
    )


# ===== КНОПКА: ВЕРСИЯ =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "version":
        version = get_timer_version()
        await query.message.reply_text(
            f"Актуальная версия таймера: {version}",
            reply_markup=main_keyboard()
        )


# ===== ОБРАБОТКА ФОТО =====
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_path = f"check_{uuid.uuid4().hex}.jpg"

    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        await tg_file.download_to_drive(temp_path)

        img = Image.open(temp_path)

        text = pytesseract.image_to_string(
            img,
            lang="rus+eng"
        ).lower()

        print("OCR TEXT:", text)

        has_channel = "firecube" in text
        has_sub = (
            "вы подписаны" in text
            or "подписаны" in text
            or "subscribed" in text
        )

        if has_channel and has_sub:
            with open(FILE_PATH, "rb") as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename="CubeTimer.html",
                    caption="Доступ подтверждён 🔥 Вот твой файл."
                )
        else:
            await update.message.reply_text(
                "Не удалось подтвердить подписку.\n"
                "Убедись, что на скрине чётко видно канал FireCube и статус подписки.",
                reply_markup=main_keyboard()
            )

    except Exception as e:
        print("ERROR:", e)
        await update.message.reply_text("Ошибка обработки изображения.")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ===== MAIN =====
def main():
    if not TOKEN:
        print("BOT_TOKEN не найден")
        return
    if not os.path.exists(FILE_PATH):
        print(f"Файл не найден: {FILE_PATH}")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
