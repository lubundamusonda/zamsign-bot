import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Load env
load_dotenv()

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# States
(
    AGREEMENT_TITLE,
    AGREEMENT_TERMS,
    AGREEMENT_AMOUNT,
    AGREEMENT_PARTY_SEARCH,
    SIGNATURE_NAME,
    SIGNATURE_NRC,
) = range(6)


# ------------------ HELPERS ------------------ #
async def send_message(update: Update, text: str, reply_markup=None):
    """Safe send (handles message vs callback)"""
    if update.message:
        return await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        return await update.callback_query.edit_message_text(
            text, reply_markup=reply_markup
        )


# ------------------ COMMANDS ------------------ #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Initiate Agreement", callback_data="initiate")],
        [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
        [InlineKeyboardButton("📤 Outbox", callback_data="outbox")],
    ]

    await send_message(
        update,
        "👋 Welcome to ZamSign\nYour digital agreement platform.\n\nChoose an option:",
        InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(
        update,
        "/start - Dashboard\n/help - Help\n/cancel - Cancel process",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(update, "❌ Cancelled.")
    return ConversationHandler.END


# ------------------ FLOW ------------------ #
async def initiate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(update, "📄 Enter agreement title:")
    return AGREEMENT_TITLE


async def agreement_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("📝 Enter terms:")
    return AGREEMENT_TERMS


async def agreement_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["terms"] = update.message.text
    await update.message.reply_text("💰 Enter amount (ZMW):")
    return AGREEMENT_AMOUNT


async def agreement_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = float(update.message.text)
        await update.message.reply_text("👤 Enter counterparty username:")
        return AGREEMENT_PARTY_SEARCH
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number:")
        return AGREEMENT_AMOUNT


async def search_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.replace("@", "")
    context.user_data["counterparty"] = username

    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_counterparty")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]

    await update.message.reply_text(
        f"Confirm counterparty: @{username}?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return AGREEMENT_PARTY_SEARCH


async def confirm_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(update, "✍️ Enter your full name:")
    return SIGNATURE_NAME


async def capture_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🆔 Enter NRC:")
    return SIGNATURE_NRC


async def capture_nrc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nrc"] = update.message.text

    document = generate_document(context.user_data)

    await update.message.reply_text("✅ Agreement Created:\n\n" + document)

    return ConversationHandler.END


# ------------------ DOCUMENT ------------------ #
def generate_document(data: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""
SALE AGREEMENT

Date: {timestamp}

Seller: {data.get("name")}
NRC: {data.get("nrc")}

Buyer: {data.get("counterparty")}

Title: {data.get("title")}

Terms:
{data.get("terms")}

Amount: ZMW {data.get("amount")}
"""


# ------------------ MAIN ------------------ #
def main():
    token = os.getenv("BOT_TOKEN")
    url = os.getenv("RENDER_EXTERNAL_URL")
    port = int(os.getenv("PORT", 10000))

    if not token:
        raise ValueError("BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Conversation
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(initiate, pattern="^initiate$")],
        states={
            AGREEMENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_title)],
            AGREEMENT_TERMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_terms)],
            AGREEMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_amount)],
            AGREEMENT_PARTY_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_counterparty),
                CallbackQueryHandler(confirm_counterparty, pattern="^confirm_counterparty$")
            ],
            SIGNATURE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, capture_name)],
            SIGNATURE_NRC: [MessageHandler(filters.TEXT & ~filters.COMMAND, capture_nrc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)

    # Webhook
    webhook_url = f"{url}/{token}"

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=token,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()