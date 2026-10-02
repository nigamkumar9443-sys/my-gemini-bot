import os
import time
from io import BytesIO
from PIL import Image

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from google import genai
from google.genai import types

# Tokens environment variables se load honge
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

CHAT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "imagen-3.0-generate-002"
VIDEO_MODEL = "veo-2.0-generate-001"

chat_sessions = {}

def get_or_create_chat(user_id: int):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = client.chats.create(
            model=CHAT_MODEL,
            config=types.GenerateContentConfig(
                system_instruction="Aap ek helpful, smart AI assistant hain jaise official Google Gemini.",
                tools=[{"google_search": {}}],
            ),
        )
    return chat_sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_sessions[user_id] = client.chats.create(
        model=CHAT_MODEL,
        config=types.GenerateContentConfig(
            system_instruction="Aap ek helpful, smart AI assistant hain jaise official Google Gemini.",
            tools=[{"google_search": {}}],
        ),
    )
    msg = (
        "👋 **Namaste! Main Gemini AI Bot hoon.**\n\n"
        "• 💬 Chat / Sawal-Jawab\n"
        "• 🌐 Web Search\n"
        "• 🖼 Photo & PDF Analysis\n"
        "• 🎙 Voice Messages\n"
        "• 🎨 `/image <prompt>`\n"
        "• 🎥 `/video <prompt>`\n\n"
        "Reset ke liye: `/clear`"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in chat_sessions:
        del chat_sessions[user_id]
    await update.message.reply_text("Chat memory reset kar di gayi hai!")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kripya prompt dein: `/image a futuristic city`", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        result = client.models.generate_images(
            model=IMAGE_MODEL,
            prompt=prompt,
            config=dict(number_of_images=1, aspect_ratio="1:1")
        )
        for gen_img in result.generated_images:
            stream = BytesIO(gen_img.image.image_bytes)
            stream.seek(0)
            await update.message.reply_photo(photo=stream, caption=f"Prompt: {prompt}")
    except Exception as e:
        await update.message.reply_text(f"Image error: {str(e)}")

async def generate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kripya prompt dein: `/video ocean waves`", parse_mode=ParseMode.MARKDOWN)
        return

    status = await update.message.reply_text("Video render ho rahi hai (1-2 min)...")
    await update.message.chat.send_action(ChatAction.RECORD_VIDEO)
    try:
        op = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=prompt,
            config=dict(aspect_ratio="16:9", duration_seconds=5)
        )
        while not op.done:
            time.sleep(10)
            op = client.operations.get(op)

        vid = op.response.generated_videos[0]
        stream = BytesIO(vid.video.video_bytes)
        stream.seek(0)
        await update.message.reply_video(video=stream, caption=f"Prompt: {prompt}")
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Video error: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = get_or_create_chat(user_id)
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        res = chat.send_message(update.message.text)
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = get_or_create_chat(user_id)
    caption = update.message.caption or "Explain this image."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        photo = await update.message.photo[-1].get_file()
        stream = BytesIO()
        await photo.download_to_memory(stream)
        stream.seek(0)
        img = Image.open(stream)
        res = chat.send_message([img, caption])
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    caption = update.message.caption or "Document summarize karein."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        doc_file = await doc.get_file()
        file_bytes = await doc_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(file_bytes), mime_type=doc.mime_type or "application/pdf")
        res = client.models.generate_content(model=CHAT_MODEL, contents=[part, caption])
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    user_id = update.effective_user.id
    chat = get_or_create_chat(user_id)
    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    try:
        voice_file = await voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(audio_bytes), mime_type="audio/ogg")
        res = chat.send_message([part, "Audio ka context samajh kar jawab dein."])
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("image", generate_image))
    app.add_handler(CommandHandler("video", generate_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.run_polling()
