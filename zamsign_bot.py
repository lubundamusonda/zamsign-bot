import logging
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
AGREEMENT_TITLE, AGREEMENT_TERMS, AGREEMENT_AMOUNT, AGREEMENT_PARTY_SEARCH, \
COUNTERPARTY_DETAILS, WITNESS_DETAILS, SIGNATURE_CAPTURE, CONFIRM_COMPLETION, \
PAYMENT_CONFIRMATION = range(9)

# In-memory storage (replace with database in production)
agreements = {}
users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message and main dashboard"""
    keyboard = [
        [InlineKeyboardButton("📝 Initiate Agreement", callback_data='initiate')],
        [InlineKeyboardButton("📥 Inbox", callback_data='inbox')],
        [InlineKeyboardButton("📤 Outbox", callback_data='outbox')],
        [InlineKeyboardButton("🔄 In Progress", callback_data='in_progress')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Welcome to ZamSign!\n"
        "Your digital agreement platform.\n\n"
        "What would you like to do today?",
        reply_markup=reply_markup
    )

async def initiate_agreement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a new agreement"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📄 Let's create a new agreement!\n"
        "Please enter the agreement title:"
    )
    return AGREEMENT_TITLE

async def agreement_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store agreement title and ask for terms"""
    context.user_data['agreement_title'] = update.message.text
    await update.message.reply_text(
        "📝 Please enter the agreement terms/conditions:"
    )
    return AGREEMENT_TERMS

async def agreement_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store terms and ask for amount"""
    context.user_data['agreement_terms'] = update.message.text
    await update.message.reply_text(
        "💰 Please enter the agreement amount (in ZMW):"
    )
    return AGREEMENT_AMOUNT

async def agreement_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store amount and ask for counterparty"""
    try:
        amount = float(update.message.text)
        context.user_data['agreement_amount'] = amount
        
        await update.message.reply_text(
            "👥 Please enter the Telegram username or ID of the counterparty:"
        )
        return AGREEMENT_PARTY_SEARCH
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number:"
        )
        return AGREEMENT_AMOUNT

async def search_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for counterparty (mock implementation)"""
    username = update.message.text.strip('@')
    context.user_data['counterparty_username'] = username
    
    # Mock user data - in production, this would search a database
    mock_users = {
        'john_doe': {'name': 'John Doe', 'nrc': '123456/78/1'},
        'jane_smith': {'name': 'Jane Smith', 'nrc': '789012/34/1'}
    }
    
    if username in mock_users:
        user_data = mock_users[username]
        context.user_data['counterparty_data'] = user_data
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data='confirm_counterparty')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Found user: {user_data['name']}\n"
            f"NRC: {user_data['nrc']}\n\n"
            "Confirm this counterparty?",
            reply_markup=reply_markup
        )
        return AGREEMENT_PARTY_SEARCH
    else:
        await update.message.reply_text(
            "❌ User not found. Please try again or enter their details manually:"
        )
        return AGREEMENT_PARTY_SEARCH

async def confirm_counterparty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm counterparty and start signing process"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✍️ Please enter your full name for signing:"
    )
    return SIGNATURE_CAPTURE

async def capture_signature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture signature details"""
    context.user_data['initiator_name'] = update.message.text
    await update.message.reply_text(
        "🆔 Please enter your NRC number:"
    )
    return SIGNATURE_CAPTURE

async def generate_agreement_document(agreement_data):
    """Generate the agreement document with QR code"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    document = f"""
SALE AND PURCHASE AGREEMENT

THIS AGREEMENT
This is an Agreement of Sale made on this {timestamp}, between the following parties:

1. PARTIES
Seller
Full Name: {agreement_data.get('initiator_name', 'N/A')}
NRC Number: {agreement_data.get('initiator_nrc', 'N/A')}
Residential Address: {agreement_data.get('initiator_address', 'N/A')}

Buyer
Full Name: {agreement_data.get('counterparty_name', 'N/A')}
NRC Number: {agreement_data.get('counterparty_nrc', 'N/A')}
Residential Address: {agreement_data.get('counterparty_address', 'N/A')}

2. AGREEMENT TITLE
{agreement_data.get('title', 'N/A')}

3. DESCRIPTION OF ITEM / CONDITIONS
The Seller agrees to sell, and the Buyer agrees to purchase the item(s) under the terms below:
{agreement_data.get('terms', 'N/A')}

4. PURCHASE PRICE
Amount: ZMW {agreement_data.get('amount', '0.00')}

5. TERMS AND CONDITIONS
1. Seller confirms rightful ownership.
2. Buyer accepts item condition.
3. Transaction final upon payment.
4. Additional conditions as stated above.

6. BILL OF SALE CONFIRMATION
The parties signed a Bill of Sale for the item(s) being bought and sold.

7. DECLARATION
Both parties confirm agreement and accuracy of information.

8. SIGNATURES
Seller Signature: {agreement_data.get('initiator_signature', '[SIGNATURE]')}
Buyer Signature: {agreement_data.get('counterparty_signature', '[SIGNATURE]')}

9. VERIFICATION
This document was generated via ZamSign. Scan QR code to verify.
Agreement ID: ZS-{timestamp.replace(' ', '').replace(':', '')[:12]}
"""
    
    return document

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    await update.message.reply_text("❌ Agreement creation cancelled.")
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'initiate':
        return await initiate_agreement(update, context)
    elif query.data == 'confirm_counterparty':
        return await confirm_counterparty(update, context)
    elif query.data == 'cancel':
        await query.edit_message_text("❌ Operation cancelled.")
        return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = """
🤖 ZamSign Bot Commands:

/start - Show main dashboard
/help - Show this help message
/cancel - Cancel current operation

💡 How to use:
1. Start by clicking "Initiate Agreement"
2. Fill in agreement details
3. Search for counterparty
4. Both parties sign digitally
5. Complete and pay service fee
6. Get verified document with QR code
"""
    await update.message.reply_text(help_text)

if __name__ == '__main__':
    BOT_TOKEN = os.environ.get("8735695688:AAGtUGEyw3mmm42v8YgS87M81HRHPEsU-CI", "")
    PORT = int(os.environ.get("PORT", "10000"))
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not set")
        raise SystemExit(1)

    if not RENDER_EXTERNAL_URL:
        print("❌ ERROR: RENDER_EXTERNAL_URL not set")
        raise SystemExit(1)

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^initiate$')],
        states={
            AGREEMENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_title)],
            AGREEMENT_TERMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_terms)],
            AGREEMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, agreement_amount)],
            AGREEMENT_PARTY_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_counterparty),
                CallbackQueryHandler(button_handler, pattern='^confirm_counterparty$')
            ],
            SIGNATURE_CAPTURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, capture_signature)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))

    webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/{BOT_TOKEN}"

    print("✅ Starting ZamSign bot...")
    print(f"🔧 Port: {PORT}")
    print(f"🔗 Webhook URL: {webhook_url}")

    try:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
            allowed_updates=None
        )
    except Exception as e:
        print(f"❌ Failed to start webhook: {str(e)}")
        raise SystemExit(1)