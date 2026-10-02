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

# Free Tier par sabse reliable aur stable models
MODELS_PRIORITY = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

chat_histories = {}

def generate_ai_response(contents):
    last_err = None
    for model_name in MODELS_PRIORITY:
        try:
            config = types.GenerateContentConfig(
                system_instruction=(
                    "Aap Google Gemini AI hain. Aapka vyavhar ekdum polite, professional, aur helpful hona chahiye. "
                    "Hinglish ya Hindi mein swachh formatting ke saath point-to-point uttar dein."
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
    
    welcome_banner = (
        f"✨ **Hello, {user_name}! Main hoon Gemini.**\n\n"
        "Aapka personal AI assistant—sochne, seekhne aur naye ideas create karne ke liye tayyar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ **Main kya-kya kar sakta hoon?**\n"
        "💬 **Smart Chat:** Sawal poochein, topics samjhein ya code likhwayein\n"
        "🎨 **AI Art:** `/image <prompt>` likh kar nayi photos banwayein\n"
        "📷 **Vision:** Koi bhi photo bhej kar sawal poochein\n"
        "📄 **Docs & PDF:** Files summarize karwayein\n"
        "🎙 **Voice:** Voice note bhej kar baat karein\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 *Shuruat ke liye niche kuch bhi type karein ya command select karein:* `/help` | `/clear`"
    )
    await update.message.reply_text(welcome_banner, parse_mode=ParseMode.MARKDOWN)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    await update.message.reply_text("🧹 *Chat history reset ho gayi hai. Naye sawal ke saath shuru karein!*", parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_ui = (
        "🛠 **Gemini Guide & Commands**\n\n"
        "• `/image <prompt>` - AI Generated High Quality Image\n"
        "• `/clear` ya `/reset` - Purani baatein clear karein\n"
        "• `/model` - Active model status\n"
        "• **Photo/Document:** Seedha chat mein attach karein\n"
        "• **Voice:** Telegram mic se bol kar bhej dein"
    )
    await update.message.reply_text(help_ui, parse_mode=ParseMode.MARKDOWN)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ Powered by **Google Gemini High-Availability Engine**.", parse_mode=ParseMode.MARKDOWN)

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Video generator tool agle update mein activate hoga!")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️️ Kripya description dein:\n`/image a sports car in neon lights`", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        await update.message.reply_photo(photo=image_url, caption=f"🎨 *Generated for:* `{prompt}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Image error: {str(e)}")

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

        reply = generate_ai_response(formatted)
        chat_histories[user_id].append({"role": "model", "parts": [reply]})
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("Thoda wait karke dubara bhejein, servers par load zyada tha.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or "Analyze this image and explain what is in it."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        photo = await update.message.photo[-1].get_file()
        stream = BytesIO()
        await photo.download_to_memory(stream)
        stream.seek(0)
        img = Image.open(stream)

        reply = generate_ai_response([img, caption])
        await update.message.reply_text(reply)
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

        reply = generate_ai_response([part, caption])
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    try:
        voice_file = await voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(audio_bytes), mime_type="audio/ogg")

        reply = generate_ai_response([part, "Audio ko dhyan se sun kar point-to-point jawab dein."])
        await update.message.reply_text(reply)
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
