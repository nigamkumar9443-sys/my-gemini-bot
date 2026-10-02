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

# Railway ke Variables se Token aayega
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 👇 APNA LINK AUR USERNAME YAHAN DALO (Agar alag hai toh quotes ke andar change kar lena)
CHANNEL_LINK = "https://t.me/AapkeChannelKaLink"  # e.g. https://t.me/your_channel
ADMIN_USERNAME = "AapkaUsername"                  # e.g. nigamkumar (bina @ ke)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Namaste!**\n\n"
        "Main ek **Professional Welcome Bot** hoon. 🤖✨\n"
        "Mujhe apne Telegram Group me add karein aur **Admin** banayein. "
        "Jaise hi koi naya member group join karega, main unka grand welcome karunga! 🎉",
        parse_mode=ParseMode.MARKDOWN
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        # Bot khud ka welcome na kare
        if member.id == context.bot.id:
            continue

        first_name = member.first_name or "Dost"
        username = f"@{member.username}" if member.username else "N/A"
        user_id = member.id
        join_time = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
        group_name = update.effective_chat.title or "Hamare Group"

        # Welcome Card UI with details and emojis
        welcome_card = (
            f"🎉━━━━━━━━━━━━━━━━━━━🎉\n"
            f"   ✨ **WELCOME TO THE GROUP** ✨\n"
            f"🎉━━━━━━━━━━━━━━━━━━━🎉\n\n"
            f"👋 **Namaste, {first_name}!**\n"
            f"Aapka **{group_name}** me tahe dil se swagat hai! 🌟🚀\n\n"
            f"📋 **Member Details:**\n"
            f"👤 **Name:** {first_name}\n"
            f"🏷️ **Username:** {username}\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"⏰ **Joined At:** {join_time}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Rules:**\n"
            f"• Kisi ke sath badtameezi na karein 🤝\n"
            f"• Spam ya 18+ links allow nahi hain 🚫\n"
            f"• Shanti aur samman banaye rakhein 🕊️\n\n"
            f"📢 *Naye updates aur special contents ke liye hamara official channel zaroor join karein!* 👇"
        )

        # Clickable Buttons
        keyboard = [
            [
                InlineKeyboardButton("📢 Join Official Channel", url=https://t.me/DARKGLOBALNET),
            ],
            [
                InlineKeyboardButton("👤 Contact Admin", url=f"https://t.me/{@V2NEXUSPRIME}"),
            ]
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
    
    print("Welcome Bot successfully running...")
    app.run_polling()
    
