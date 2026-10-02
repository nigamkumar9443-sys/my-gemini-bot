
import os
import asyncio
import logging
from io import BytesIO

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from google import genai
from google.genai import types

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN aur GEMINI_API_KEY .env mein set karo."
    )

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nexus-ai")

client = genai.Client(api_key=GEMINI_API_KEY)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

user_models = {}
chat_history = {}
MAX_HISTORY = 12


def get_model(user_id):
    return user_models.get(user_id, DEFAULT_MODEL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 AI Chat", callback_data="chat")],
        [InlineKeyboardButton("📚 Available Models", callback_data="models")],
        [InlineKeyboardButton("🖼️ Image Input Help", callback_data="image")],
        [InlineKeyboardButton("🎬 Video AI Help", callback_data="video")],
        [InlineKeyboardButton("🔄 Reset Chat", callback_data="reset")],
    ]

    await update.message.reply_text(
        "⚡ NEXUS AI BOT\n\n"
        "AI chat, model selection, image analysis aur supported "
        "generation tools.\n\n"
        "Commands:\n"
        "/models - Available models\n"
        "/model MODEL_ID - Change model\n"
        "/reset - Clear chat history\n"
        "/video - Video generation help",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Loading available models...")

    try:
        models = await asyncio.to_thread(lambda: list(client.models.list()))
        lines = []

        for model in models:
            name = getattr(model, "name", None)
            if name:
                lines.append(name)

        if not lines:
            await msg.edit_text("No models returned by the API.")
            return

        text = "📚 AVAILABLE GEMINI MODELS\n\n" + "\n".join(lines[:80])
        text += "\n\nUse /model MODEL_ID to select a model."

        for chunk_start in range(0, len(text), 3500):
            chunk = text[chunk_start:chunk_start + 3500]
            if chunk_start == 0:
                await msg.edit_text(chunk)
            else:
                await update.effective_chat.send_message(chunk)

    except Exception as exc:
        log.exception("Model listing failed")
        await msg.edit_text(f"Model list error: {exc}"[:3500])


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"Current model: {get_model(update.effective_user.id)}\n"
            "Usage: /model gemini-2.5-flash"
        )
        return

    requested = context.args[0].strip()
    if requested.startswith("models/"):
        requested = requested.split("/", 1)[1]

    user_models[update.effective_user.id] = requested
    await update.message.reply_text(f"✅ Selected model: {requested}")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_history.pop(update.effective_user.id, None)
    await update.message.reply_text("♻️ Chat history cleared.")


async def generate_reply(user_id: int, prompt: str, image_bytes=None, mime_type=None):
    model = get_model(user_id)
    history = chat_history.setdefault(user_id, [])

    contents = []
    for item in history[-MAX_HISTORY:]:
        contents.append(
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])],
            )
        )

    parts = [types.Part.from_text(text=prompt)]

    if image_bytes:
        parts.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type or "image/jpeg",
            )
        )

    contents.append(types.Content(role="user", parts=parts))

    response = await asyncio.to_thread(
        lambda: client.models.generate_content(
            model=model,
            contents=contents,
        )
    )

    answer = response.text or "The model returned no text."
    history.extend([
        {"role": "user", "text": prompt},
        {"role": "model", "text": answer},
    ])
    chat_history[user_id] = history[-MAX_HISTORY:]
    return answer


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id

    status = await message.reply_text("⚡ Thinking...")

    try:
        image_bytes = None
        mime_type = None
        prompt = message.caption or message.text or "Describe this image."

        if message.photo:
            photo = await message.photo[-1].get_file()
            data = await photo.download_as_bytearray()
            image_bytes = bytes(data)
            mime_type = "image/jpeg"

        elif message.document:
            document = message.document
            if document.mime_type and document.mime_type.startswith("image/"):
                file = await document.get_file()
                image_bytes = bytes(await file.download_as_bytearray())
                mime_type = document.mime_type
            else:
                await status.edit_text(
                    "This version accepts text and image files. "
                    "PDF/document processing is not enabled."
                )
                return

        answer = await generate_reply(
            user_id, prompt, image_bytes, mime_type
        )

        for start_index in range(0, len(answer), 4000):
            chunk = answer[start_index:start_index + 4000]
            if start_index == 0:
                await status.edit_text(chunk)
            else:
                await message.reply_text(chunk)

    except Exception:
        log.exception("Message processing failed")
        await status.edit_text(
            "❌ Request failed. Check your API key, model access, "
            "quota and network connection."
        )


async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 VIDEO AI\n\n"
        "Video generation requires a compatible video-generation model "
        "and API access. A regular chat model cannot generate videos.\n\n"
        "Configure a supported Veo model in your Google GenAI integration "
        "before enabling video generation."
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "models":
        await query.edit_message_text(
            "Run /models to list models available to your API key."
        )
    elif query.data == "reset":
        chat_history.pop(query.from_user.id, None)
        await query.edit_message_text("♻️ Chat history cleared.")
    elif query.data == "image":
        await query.edit_message_text(
            "🖼️ Send a photo with a question to analyze it."
        )
    elif query.data == "video":
        await query.edit_message_text(
            "🎬 Use /video for video-generation requirements."
        )
    else:
        await query.edit_message_text(
            "🧠 Send a message to start chatting with AI."
        )


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("models", models_command))
    application.add_handler(CommandHandler("model", model_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("video", video_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.Document.IMAGE)
            & ~filters.COMMAND,
            handle_message,
        )
    )

    log.info("NEXUS AI BOT starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
    
