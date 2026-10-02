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

# Tokens from Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Free Tier & Highly Stable Model Sequence
MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]

chat_histories = {}

def get_gemini_reply(contents):
    """Reliable fallback system to bypass 503 High Demand & 404 errors"""
    last_err = None
    for model_name in MODELS:
        try:
            config = types.GenerateContentConfig(
                system_instruction=(
                    "Aap Google Gemini AI hain. Hamesha polite, accurate aur stylish Hinglish me jawab dein. "
                    "Jawab me relevant emojis ka acche se upayog karein aur points ko sundar format karein."
                )
            )
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_err = e
            continue
    raise last_err

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Friend"
    chat_histories[user_id] = []

    welcome_ui = (
        f"✨ **Namaste, {user_name}! Main hoon Gemini.** ✨\n\n"
        "Main Google ke sabse powerful AI ecosystem dwara sanchalit aapka personal assistant hoon. "
        "Aapki har zaroorat—sochne, seekhne, code karne aur visuals banane ke liye bilkul taiyaar! 🚀\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 **Main aapki kya madad kar sakta hoon?**\n\n"
        "💬 **Smart Chat:** Sawal poochein, baatein karein, ya script/code likhwayein 🧠\n"
        "🎨 **AI Art:** `/image <prompt>` likhein aur instant HD images banwayein 🖼️\n"
        "📷 **Vision:** Koi bhi photo bhej kar uska vivaran ya solution jaanein 🔍\n"
        "📑 **Doc & PDF:** Badi files summarize karwayein aur sawal poochein 📊\n"
        "🎙️ **Voice Notes:** Telegram voice bhej kar direct aawaz me baat karein 🎧\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ **Quick Controls:**\n"
        "• `/clear` - Purani baatein bhulane ke liye 🧹\n"
        "• `/help` - Sabhi features aur guide ke liye ℹ️\n\n"
        "👇 *Neeche seedha apna sawal type karein ya koi photo bhejein!*"
    )
    await update.message.reply_text(welcome_ui, parse_mode=ParseMode.MARKDOWN)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    await update.message.reply_text("🧹 **Chat memory reset kar di gayi hai!**\nAb hum ekdum naye sire se baat kar sakte hain. ✨", parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_ui = (
        "📖 **Gemini AI User Guide & Commands** 🛠️\n\n"
        "• `/start` 🚀 - Bot ko refresh karke shuru karein\n"
        "• `/image <prompt>` 🎨 - Nayi photo banayein (e.g. `/image flying car neon city`)\n"
        "• `/clear` ya `/reset` 🧹 - Purani chat memory clear karein\n"
        "• `/model` ⚡ - Active AI Engine ki jankari\n"
        "• `/video` 🎬 - Video generation status\n\n"
        "💡 *Tips:* Photo, Document ya Voice bhejne ke liye direct chat me upload karein, kisi slash command ki zaroorat nahi hai!"
    )
    await update.message.reply_text(help_ui, parse_mode=ParseMode.MARKDOWN)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **Google Gemini High-Performance Neural Engine** 🟢\n"
        "Status: `Online & Ready`\n"
        "Redundancy: `Active Failover Engine` 🛡️",
        parse_mode=ParseMode.MARKDOWN
    )

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 **Gemini Veo / Video Engine:** Testing phase mein hai aur agle build mein activate hoga! ⏳")

# 100% Free Image Generator (No Quota limits)
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ **Prompt missing!**\nKripya aise likhein: `/image a cute white cat playing guitar` 🐱🎸", parse_mode=ParseMode.MARKDOWN)
        return

    status = await update.message.reply_text("🎨 *Aapki imagination render ki ja rahi hai... Kripya thoda intezaar karein!* ⏳", parse_mode=ParseMode.MARKDOWN)
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)

    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
        await update.message.reply_photo(photo=url, caption=f"✨ **AI Art Generated!**\n🎨 Prompt: `{prompt}`", parse_mode=ParseMode.MARKDOWN)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ **Image error:** `{str(e)}`")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_msg = update.message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({"role": "user", "parts": [user_msg]})
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        formatted = []
        for msg in chat_histories[user_id]:
            formatted.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=p) for p in msg["parts"]],
                )
            )

        reply = get_gemini_reply(formatted)
        chat_histories[user_id].append({"role": "model", "parts": [reply]})
        await update.message.reply_text(reply)
    except Exception:
        await update.message.reply_text("⚡ Google ke server par load zyada tha, kripya 3-4 second baad wapas bhejein! 🙏")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or "Analyze this image in detail and describe what you see."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        photo = await update.message.photo[-1].get_file()
        stream = BytesIO()
        await photo.download_to_memory(stream)
        stream.seek(0)
        img = Image.open(stream)

        reply = get_gemini_reply([img, caption])
        await update.message.reply_text(f"🔍 **Analysis:**\n\n{reply}")
    except Exception as e:
        await update.message.reply_text(f"❌ **Photo scan error:** `{str(e)}`")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    caption = update.message.caption or "Is document ko summarise karein aur main points batayein."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        doc_file = await doc.get_file()
        file_bytes = await doc_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(file_bytes), mime_type=doc.mime_type or "application/pdf")

        reply = get_gemini_reply([part, caption])
        await update.message.reply_text(f"📑 **Document Summary:**\n\n{reply}")
    except Exception as e:
        await update.message.reply_text(f"❌ **File error:** `{str(e)}`")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    try:
        voice_file = await voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(audio_bytes), mime_type="audio/ogg")

        reply = get_gemini_reply([part, "Audio ko dhyan se sunkar acche emojis ke saath uttar dein."])
        await update.message.reply_text(f"🎙️ **Gemini Response:**\n\n{reply}")
    except Exception as e:
        await update.message.reply_text(f"❌ **Audio process error:** `{str(e)}`")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("reset", clear))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("video", video_cmd))
    app.add_handler(CommandHandler("image", generate_image))
    
    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    
    app.run_polling()
