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

# Primary & Fallback Models taaki 503 error kabhi na ruke
PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

chat_histories = {}

def call_gemini_with_fallback(contents, system_instruction=None):
    models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
    last_error = None

    for model_name in models_to_try:
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction or "Aap ek helpful, smart AI assistant hain. Roman Hindi/Hinglish me friendly jawab dein."
            )
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            return response.text
        except Exception as e:
            last_error = e
            continue

    raise last_error

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    msg = (
        "Namaste! Main **Gemini AI Bot** hoon.\n\n"
        "• Sawal-Jawab aur Chat\n"
        "• Photos & Docs Analysis\n"
        "• Voice Notes\n"
        "• AI Image banana: `/image <prompt>`\n\n"
        "Reset chat ke liye: `/clear`"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_histories[user_id] = []
    await update.message.reply_text("Chat memory reset kar di gayi hai!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "**Available Commands:**\n\n"
        "• `/image <prompt>` - AI photo generate karein\n"
        "• `/clear` ya `/reset` - Context clear karein\n"
        "• `/model` - Check status\n"
        "• Direct text/photo/voice bhejein"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Active Model Pool: `{PRIMARY_MODEL}` with auto-failover.", parse_mode=ParseMode.MARKDOWN)

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Video generation feature testing phase mein hai.")

# 100% Free image generator
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Kripya description dein: `/image a futuristic city`")
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
    user_msg = update.message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({"role": "user", "parts": [user_msg]})
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Convert history format for Gemini
        formatted_contents = []
        for msg in chat_histories[user_id]:
            formatted_contents.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=p) for p in msg["parts"]],
                )
            )

        reply_text = call_gemini_with_fallback(formatted_contents)
        chat_histories[user_id].append({"role": "model", "parts": [reply_text]})
        await update.message.reply_text(reply_text)
    except Exception as e:
        await update.message.reply_text(f"Server busy hai, kripya 5 second baad dubara puchein. ({str(e)})")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or "Describe this image."
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        photo = await update.message.photo[-1].get_file()
        stream = BytesIO()
        await photo.download_to_memory(stream)
        stream.seek(0)
        img = Image.open(stream)

        reply_text = call_gemini_with_fallback([img, caption])
        await update.message.reply_text(reply_text)
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

        reply_text = call_gemini_with_fallback([part, caption])
        await update.message.reply_text(reply_text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    try:
        voice_file = await voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        part = types.Part.from_bytes(data=bytes(audio_bytes), mime_type="audio/ogg")

        reply_text = call_gemini_with_fallback([part, "Audio ko sun kar Roman Hindi me jawab dein."])
        await update.message.reply_text(reply_text)
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
