import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

CHANNEL_URL = "https://t.me/DARKGLOBALNET"
ADMIN_URL = "https://t.me/V2NEXUSPRIME"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **Namaste! Main Welcome Bot hoon.** ✨\n\n"
        "Mujhe apne Telegram group me add karke **Admin** banayein. "
        "Jaise hi koi naya member aayega, main unka welcome karunga! 🎉"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        first_name = member.first_name or "Member"
        username = f"@{member.username}" if member.username else "N/A"
        user_id = member.id
        join_time = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
        group_name = update.effective_chat.title or "Hamare Group"

        welcome_card = (
            f"🎉━━━━━━━━━━━━━━━━━━━🎉\n"
            f"   ✨ **WELCOME TO THE GROUP** ✨\n"
            f"🎉━━━━━━━━━━━━━━━━━━━🎉\n\n"
            f"👋 Namaste, **{first_name}**!\n"
            f"Aapka **{group_name}** me tahe dil se swagat hai! 🌟🚀\n\n"
            f"📋 **Member Details:**\n"
            f"👤 Name: {first_name}\n"
            f"🏷️ Username: {username}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"⏰ Joined At: {join_time}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Rules:**\n"
            f"• Respect all members 🤝\n"
            f"• No spam / links 🚫\n"
            f"• Follow community guidelines 🕊️\n\n"
            f"📢 Naye updates ke liye official channel zaroor join karein! 👇"
        )

        keyboard = [
            [InlineKeyboardButton("📢 Join Official Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("👤 Contact Admin", url=ADMIN_URL)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_card,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.run_polling()
    
