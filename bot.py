import os
import re
import uuid
import base64
import httpx

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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FILE_PATH = "files/current.html"


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


# ===== ПРОВЕРКА ПОДПИСКИ ЧЕРЕЗ CLAUDE VISION =====
async def check_subscription_with_claude(image_bytes: bytes) -> tuple[bool, str]:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 256,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Это скриншот с YouTube. Твоя задача — определить:\n"
                            "1. Виден ли на скриншоте канал с названием FireCube (или похожим)?\n"
                            "2. Видно ли, что пользователь подписан на этот канал "
                            "(кнопка 'Подписаны', 'Subscribed', колокольчик активен, "
                            "или другой явный признак подписки)?\n\n"
                            "Ответь строго в формате:\n"
                            "CHANNEL: YES или NO\n"
                            "SUBSCRIBED: YES или NO\n"
                            "REASON: одна короткая фраза — что именно ты увидел или не увидел"
                        ),
                    },
                ],
            }
        ],
    }

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    result_text = response.json()["content"][0]["text"].strip()
    print("Claude Vision response:", result_text)

    lines = result_text.upper().splitlines()
    has_channel = any("CHANNEL: YES" in line for line in lines)
    has_sub = any("SUBSCRIBED: YES" in line for line in lines)

    reason = ""
    for line in result_text.splitlines():
        if line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[-1].strip()
            break

    return (has_channel and has_sub), reason


# ===== ОБРАБОТКА ФОТО =====
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_path = f"check_{uuid.uuid4().hex}.jpg"

    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        await tg_file.download_to_drive(temp_path)

        with open(temp_path, "rb") as f:
            image_bytes = f.read()

        await update.message.reply_text("Проверяю скриншот... ⏳")

        is_subscribed, reason = await check_subscription_with_claude(image_bytes)
        print(f"Subscription check: {is_subscribed} | Reason: {reason}")

        if is_subscribed:
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

    except httpx.HTTPStatusError as e:
        print("Claude API error:", e)
        await update.message.reply_text("Ошибка при обращении к сервису проверки. Попробуй позже.")

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
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY не найден")
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
