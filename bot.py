cat > bot.py <<'PY'
import os
import io
import time
import asyncio
import logging
import tempfile
import mimetypes
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from google import genai
from google.genai import types

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "veo-3.1-generate-preview")
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "15"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

if not TOKEN or not API_KEY:
    raise SystemExit("ERROR: .env mein Telegram token aur Gemini API key bharo.")

ai = genai.Client(api_key=API_KEY)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("nexus-ai")

# Per-user settings; in-memory only.
user_models = {}
chat_history = {}
pending_image = set()
pending_video = set()
MAX_HISTORY_MESSAGES = 12


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 AI Chat", callback_data="chat"),
            InlineKeyboardButton("📚 Models", callback_data="models"),
        ],
        [
            InlineKeyboardButton("🎨 Create Image", callback_data="image"),
            InlineKeyboardButton("🎬 Create Video", callback_data="video"),
        ],
        [
            InlineKeyboardButton("📷 Analyze Photo", callback_data="photo"),
            InlineKeyboardButton("📄 Analyze File", callback_data="file"),
        ],
        [
            InlineKeyboardButton("🧹 Clear Chat", callback_data="clear"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ NEXUS AI BOT\n\n"
        "Chat, image generation, video generation, photo analysis "
        "aur document analysis use karo.\n\n"
        "Neeche menu choose karo ya seedha message bhejo.",
        reply_markup=main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 COMMANDS\n"
        "/start - Main menu\n"
        "/models - API se available models\n"
        "/model MODEL_ID - Chat model select karo\n"
        "/clear - Chat history clear karo\n\n"
        "Image: menu se Create Image chuno, phir prompt bhejo.\n"
        "Video: Create Video chuno, phir prompt bhejo.\n"
        "Photo: photo bhejo ya Analyze Photo chuno.\n"
        "Files: supported document ko Telegram par bhejo.\n\n"
        "Model list mein aana guarantee nahi karta ki har model "
        "tumhari key, quota ya region mein usable bhi hai."
    )


async def run_blocking(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def model_id(name):
    return (name or "").removeprefix("models/")


def list_models():
    result = []
    for model in ai.models.list():
        name = model_id(getattr(model, "name", ""))
        if not name:
            continue
        methods = getattr(model, "supported_actions", None) or []
        result.append((name, list(methods)))
    return sorted(result)


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text(
        "⏳ Gemini API se model list load ho rahi hai..."
    )
    try:
        models = await run_blocking(list_models)
        if not models:
            await msg.edit_text("API ne koi model return nahi kiya.")
            return

        lines = ["📚 AVAILABLE MODELS (API response)\n"]
        for name, methods in models:
            suffix = f" — {', '.join(methods)}" if methods else ""
            lines.append(f"• {name}{suffix}")
        text = "\n".join(lines)

        # Telegram message size limit guard.
        for offset in range(0, len(text), 3800):
            chunk = text[offset:offset + 3800]
            if offset == 0:
                await msg.edit_text(chunk)
            else:
                await update.effective_message.reply_text(chunk)
    except Exception as exc:
        log.exception("Model list failed")
        await msg.edit_text(f"❌ Model list nahi mili: {friendly_error(exc)}")


def friendly_error(exc):
    text = str(exc).replace(API_KEY, "[REDACTED]").replace(TOKEN, "[REDACTED]")
    low = text.lower()
    if any(x in low for x in ("403", "permission", "not authorized")):
        return "Permission nahi hai. API key, model access aur project settings check karo."
    if any(x in low for x in ("429", "quota", "resource_exhausted", "rate limit")):
        return "API quota/rate limit hit hua. Billing, quota aur limits check karo."
    if any(x in low for x in ("404", "not found")):
        return "Model ya endpoint nahi mila. /models se available model IDs check karo."
    if any(x in low for x in ("timeout", "timed out", "connection")):
        return "Network timeout hua. Internet check karke dobara try karo."
    return text[:700] or "Unknown API error."


async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /model gemini-2.5-flash\n/models se model ID dekho."
        )
        return
    chosen = context.args[0].strip()
    user_models[update.effective_user.id] = chosen
    await update.effective_message.reply_text(f"✅ Chat model set: {chosen}")


def chat_with_model(model, history, prompt):
    contents = []
    for role, text in history:
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=text)]
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    ))
    response = ai.models.generate_content(model=model, contents=contents)
    return response.text or "(Model ne text response nahi diya.)"


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = (update.effective_message.text or "").strip()
    if not prompt:
        return

    if user_id in pending_image:
        pending_image.discard(user_id)
        await generate_image(update, prompt)
        return

    if user_id in pending_video:
        pending_video.discard(user_id)
        await generate_video(update, prompt)
        return

    model = user_models.get(user_id, DEFAULT_MODEL)
    history = chat_history.get(user_id, [])

    status = await update.effective_message.reply_text("🧠 Thinking...")
    try:
        answer = await run_blocking(chat_with_model, model, history, prompt)
        history.extend([("user", prompt), ("model", answer)])
        chat_history[user_id] = history[-MAX_HISTORY_MESSAGES:]
        answer = answer[:4000]
        await status.edit_text(answer)
    except Exception as exc:
        log.exception("Chat request failed")
        await status.edit_text(f"❌ {friendly_error(exc)}")


def image_response_bytes(response):
    for part in (getattr(response, "parts", None) or []):
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data, getattr(inline, "mime_type", "image/png")
    return None, None


def create_image(prompt):
    # Gemini image model; image access depends on account/API availability.
    model = "gemini-2.5-flash-image"
    response = ai.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"]
        ),
    )
    return image_response_bytes(response), response.text or ""


async def generate_image(update: Update, prompt: str):
    status = await update.effective_message.reply_text(
        "🎨 Image generate ho rahi hai. Thoda wait karo..."
    )
    try:
        result, description = await run_blocking(create_image, prompt)
        data, mime = result
        if not data:
            extra = description[:1000] if description else "No image returned."
            await status.edit_text(
                "❌ Is model/API request se image output nahi mila.\n" + extra
            )
            return
        ext = mimetypes.guess_extension(mime or "image/png") or ".png"
        with tempfile.NamedTemporaryFile(suffix=ext) as f:
            f.write(data)
            f.flush()
            await update.effective_message.reply_photo(
                photo=Path(f.name).open("rb"),
                caption="🎨 Generated by Gemini"
            )
        await status.delete()
    except Exception as exc:
        log.exception("Image generation failed")
        await status.edit_text(f"❌ Image generation failed: {friendly_error(exc)}")


async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user_id = update.effective_user.id
    photo = msg.photo[-1] if msg.photo else None
    if not photo:
        return
    if photo.file_size and photo.file_size > MAX_FILE_BYTES:
        await msg.reply_text(f"Photo bahut badi hai. Limit: {MAX_FILE_MB} MB.")
        return

    status = await msg.reply_text("📷 Photo analyze ho rahi hai...")
    try:
        tg_file = await photo.get_file()
        raw = bytes(await tg_file.download_as_bytearray())
        image = types.Part.from_bytes(data=raw, mime_type="image/jpeg")
        model = user_models.get(user_id, DEFAULT_MODEL)
        response = await run_blocking(
            ai.models.generate_content,
            model=model,
            contents=[image, "Describe this image and answer usefully."]
        )
        await status.edit_text((response.text or "No text response.")[:4000])
    except Exception as exc:
        log.exception("Photo analysis failed")
        await status.edit_text(f"❌ Photo analysis failed: {friendly_error(exc)}")


def analyze_uploaded_file(path, prompt):
    uploaded = ai.files.upload(file=path)
    try:
        response = ai.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[uploaded, prompt]
        )
        return response.text or "No text response."
    finally:
        try:
            ai.files.delete(name=uploaded.name)
        except Exception:
            pass


async def document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    doc = msg.document
    if not doc:
        return
    if doc.file_size and doc.file_size > MAX_FILE_BYTES:
        await msg.reply_text(f"File bahut badi hai. Limit: {MAX_FILE_MB} MB.")
        return

    filename = Path(doc.file_name or "upload.bin").name
    suffix = Path(filename).suffix or ".bin"
    status = await msg.reply_text("📄 File analyze ho rahi hai...")
    try:
        tg_file = await doc.get_file()
        raw = bytes(await tg_file.download_as_bytearray())
        with tempfile.NamedTemporaryFile(suffix=suffix) as f:
            f.write(raw)
            f.flush()
            prompt = (
                "Analyze this uploaded file. Summarize its main points, "
                "extract important details, and answer in the user's language."
            )
            answer = await run_blocking(analyze_uploaded_file, f.name, prompt)
        await status.edit_text(answer[:4000])
    except Exception as exc:
        log.exception("Document analysis failed")
        await status.edit_text(
            "❌ File analyze nahi hui: " + friendly_error(exc)
            + "\nCheck karo ki file type Gemini Files API support karta hai."
        )


def create_video(prompt):
    operation = ai.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=8,
        ),
    )
    deadline = time.time() + 900
    while not operation.done:
        if time.time() > deadline:
            raise TimeoutError("Video generation timed out after 15 minutes.")
        time.sleep(10)
        operation = ai.operations.get(operation)

    response = getattr(operation, "response", None)
    if response is None:
        response = getattr(operation, "result", None)
    videos = getattr(response, "generated_videos", None) or []
    if not videos:
        raise RuntimeError("API completed but returned no generated video.")
    return videos[0].video


async def generate_video(update: Update, prompt: str):
    status = await update.effective_message.reply_text(
        "🎬 Video generation started. Isme kai minutes lag sakte hain..."
    )
    try:
        video = await run_blocking(create_video, prompt)
        # SDK versions expose generated video as a file/URI.
        uri = getattr(video, "uri", None)
        if uri:
            await status.edit_text(
                "✅ Video generation complete.\n"
                "Google API returned a video URI:\n" + str(uri)[:3000]
            )
        else:
            await status.edit_text(
                "✅ Generation complete, lekin SDK ne direct downloadable URI "
                "return nahi ki. Installed google-genai SDK ke video download "
                "method ke mutabik download support configure karna hoga."
            )
    except Exception as exc:
        log.exception("Video generation failed")
        await status.edit_text(f"❌ Video generation failed: {friendly_error(exc)}")


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data

    if action == "models":
        await query.message.reply_text(
            "Model list ke liye /models command use karo."
        )
    elif action == "chat":
        await query.message.reply_text("🧠 Apna question bhejo.")
    elif action == "image":
        pending_image.add(user_id)
        pending_video.discard(user_id)
        await query.message.reply_text("🎨 Ab image ka prompt bhejo.")
    elif action == "video":
        pending_video.add(user_id)
        pending_image.discard(user_id)
        await query.message.reply_text("🎬 Ab video ka prompt bhejo.")
    elif action == "photo":
        await query.message.reply_text("📷 Photo Telegram par bhejo.")
    elif action == "file":
        await query.message.reply_text("📄 Document/file Telegram par bhejo.")
    elif action == "clear":
        chat_history.pop(user_id, None)
        await query.message.reply_text("🧹 Chat history cleared.")
    elif action == "help":
        await query.message.reply_text(
            "Text: seedha message bhejo\n"
            "Models: /models\n"
            "Model change: /model MODEL_ID\n"
            "Photo: photo upload karo\n"
            "File: document upload karo\n"
            "Image/video: menu mein mode select karke prompt bhejo."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled Telegram error: %s", context.error)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CommandHandler("model", select_model))
    app.add_handler(CommandHandler("clear", lambda u, c: clear_command(u, c)))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
    app.add_error_handler(error_handler)
    print("NEXUS AI Bot is running...")
    app.run_polling(drop_pending_updates=True)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_history.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("🧹 Chat history cleared.")


if __name__ == "__main__":
    main()
PY
