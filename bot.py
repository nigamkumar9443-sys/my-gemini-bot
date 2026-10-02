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

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.8-flash"

# --- Start & UI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Dost"
    msg = (
        f"✨ **Namaste {name}! Main Google Gemini AI Bot hoon.** 🚀\n\n"
        "Main aapke sawalon ke jawab dene aur naye ideas create karne ke liye tayyar hoon.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **Features:**\n"
        "💬 **Chat:** Mujhse koi bhi sawal poochein ya code likhwayein 🧠\n"
        "🎨 **Image:** `/image <prompt>` likh kar nayi photo banwayein 🖼️\n"
        "📷 **Vision:** Photo bhej kar uske baare me poochein 🔍\n"
        "📑 **Docs:** PDF ya text file bhej kar summary lein 📊\n"
        "🎙️ **Voice:** Voice message bhej kar direct baat karein 🎧\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧹 Chat reset karne ke liye: `/clear`"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# --- Commands ---
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧹 **Chat memory reset kar di gayi hai!**", parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛠️ **Command Menu:**\n\n"
        "• `/image <prompt>` - AI photo generate karein 🎨\n"
        "• `/clear` ya `/reset` - Memory reset karein 🧹\n"
        "• Direct Photo, PDF ya Voice bhejein 💬"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# --- Image Generation (Free) ---
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ Image description dein: `/image a cute dog in space`")
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
        await update.message.reply_photo(photo=url, caption=f"🎨 Prompt: `{prompt}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# --- Text Chat ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        res = client.models.generate_content(
            model=MODEL_NAME,
            contents=update.message.text,
        )
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# --- Photo Scan ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or "Explain what is in this image."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        photo = await update.message.photo[-1].get_file()
        stream = BytesIO()
        await photo.download_to_memory(stream)
        stream.seek(0)
        img = Image.open(stream)
        res = client.models.generate_content(
            model=MODEL_NAME,
            contents=[img, caption],
        )
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# --- Documents ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    caption = update.message.caption or "Is document ko summarise karein."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        doc_file = await doc.get_file()
        file_bytes = await doc_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(file_bytes), mime_type=doc.mime_type or "application/pdf")
        res = client.models.generate_content(
            model=MODEL_NAME,
            contents=[part, caption],
        )
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# --- Voice ---
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    try:
        voice_file = await voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(audio_bytes), mime_type="audio/ogg")
        res = client.models.generate_content(
            model=MODEL_NAME,
            contents=[part, "Audio ko sun kar jawab dein."],
        )
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# --- Run App ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("reset", clear))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("image", generate_image))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    
    app.run_polling()
    
