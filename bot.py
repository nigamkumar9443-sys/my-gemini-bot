import os
import urllib.parse
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Google ka latest supported model
CHAT_MODEL = "gemini-3.8-flash"

chat_sessions = {}

def get_or_create_chat(user_id: int):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = client.chats.create(
            model=CHAT_MODEL,
            config=types.GenerateContentConfig(
                system_instruction="Aap ek helpful, smart AI assistant hain. Friendly andaaz me Roman Hindi/Hinglish me jawab dein."
            ),
        )
    return chat_sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_sessions[user_id] = client.chats.create(
        model=CHAT_MODEL,
        config=types.GenerateContentConfig(
            system_instruction="Aap ek helpful, smart AI assistant hain. Friendly andaaz me Roman Hindi/Hinglish me jawab dein."
        ),
    )
    msg = (
        "Namaste! Main **Gemini AI Bot** hoon.\n\n"
        "• Sawal-Jawab aur Chat karein\n"
        "• Photos & Docs bhejein\n"
        "• Voice Notes bhej kar baat karein\n"
        "• AI Image banana: `/image <prompt>`\n\n"
        "Menu commands ke liye slash `/` dabayein ya `/help` karein."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in chat_sessions:
        del chat_sessions[user_id]
    await update.message.reply_text("Chat memory reset kar di gayi hai!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "**Bot Features:**\n\n"
        "1. `/image <prompt>` - Nayi image generate karein\n"
        "2. `/clear` ya `/reset` - Memory reset karein\n"
        "3. `/model` - Active model status\n"
        "4. `/video` - Video tool status\n"
        "5. Direct Photos/PDFs bhejein summary ke liye"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Currently active AI model: `{CHAT_MODEL}`", parse_mode=ParseMode.MARKDOWN)

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Video generation feature testing phase mein hai aur jald live hoga!")

# Free Pollinations AI Image Generator
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kripya description dein: `/image a cute dog in space`")
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        await update.message.reply_photo(photo=image_url, caption=f"Prompt: {prompt}")
    except Exception as e:
        await update.message.reply_text(f"Image error: {str(e)}")

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
        res = chat.send_message([part, "Audio ko sun kar jawab dein."])
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("reset", clear))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("video", video_cmd))
    app.add_handler(CommandHandler("image", generate_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.run_polling()
