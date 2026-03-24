import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory storage for agreements (in production, use a database)
agreements = {}
users = {}

# Bot token - set this in environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8735695688:AAGtUGEyw3mmm42v8YgS87M81HRHPEsU-CI')

class Agreement:
    def __init__(self, initiator_id, title, amount, conditions, seller_name, seller_nrc, seller_address):
        self.id = f"AG{len(agreements) + 1:04d}"
        self.initiator_id = initiator_id
        self.title = title
        self.amount = amount
        self.conditions = conditions
        self.seller_name = seller_name
        self.seller_nrc = seller_nrc
        self.seller_address = seller_address
        self.buyer_id = None
        self.buyer_name = None
        self.buyer_nrc = None
        self.buyer_address = None
        self.witness_id = None
        self.witness_name = None
        self.witness_nrc = None
        self.witness_address = None
        self.seller_signature = None
        self.buyer_signature = None
        self.witness_signature = None
        self.created_at = datetime.now()
        self.status = "draft"  # draft, pending_buyer, pending_witness, completed, paid
        self.qr_code = None

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'amount': self.amount,
            'conditions': self.conditions,
            'seller_name': self.seller_name,
            'seller_nrc': self.seller_nrc,
            'seller_address': self.seller_address,
            'buyer_name': self.buyer_name,
            'buyer_nrc': self.buyer_nrc,
            'buyer_address': self.buyer_address,
            'witness_name': self.witness_name,
            'witness_nrc': self.witness_nrc,
            'witness_address': self.witness_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    users[user.id] = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    
    keyboard = [
        [KeyboardButton("📝 Initiate Agreement")],
        [KeyboardButton("📥 Inbox"), KeyboardButton("📤 Outbox")],
        [KeyboardButton("🔄 In Progress")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_message = f"""
👋 Welcome to ZamSign!

*Your Digital Agreement Platform*

💼 **Core Features:**
• Create legally binding agreements
• Digital signatures for all parties
• Optional witness verification
• QR code authentication
• Secure document generation

📱 **How to Use:**
1. Tap "Initiate Agreement" to start a new contract
2. Fill in agreement details and sign
3. Invite counterparty via Telegram
4. Complete the signing process
5. Pay service fee and download verified document

🔐 **ZamSign** - Making contracts simple, accessible, and trusted for everyone.

*Sign. Agree. Trust.*
"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📝 Initiate Agreement":
        await start_agreement_creation(update, context)
    elif text == "📥 Inbox":
        await show_inbox(update, context)
    elif text == "📤 Outbox":
        await show_outbox(update, context)
    elif text == "🔄 In Progress":
        await show_in_progress(update, context)
    else:
        await update.message.reply_text("I don't understand that command. Please use the buttons below.")

async def start_agreement_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the agreement creation process."""
    context.user_data['agreement_step'] = 'title'
    await update.message.reply_text(
        "📝 **Create New Agreement**\n\n"
        "Step 1 of 8: Enter the **Agreement Title**\n"
        "(e.g., 'Motor Vehicle Sale', 'Property Rental', 'Service Agreement')",
        parse_mode='Markdown'
    )

async def show_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show agreements waiting for user's signature."""
    user_id = update.effective_user.id
    pending_agreements = [
        agreement for agreement in agreements.values() 
        if agreement.buyer_id == user_id and agreement.status == 'pending_buyer'
    ]
    
    if not pending_agreements:
        await update.message.reply_text("📭 Your inbox is empty. No agreements waiting for your signature.")
        return
    
    message = "📥 **Your Inbox**\n\nAgreements awaiting your signature:\n\n"
    for i, agreement in enumerate(pending_agreements, 1):
        message += f"{i}. **{agreement.title}**\n"
        message += f"   • From: {agreement.seller_name}\n"
        message += f"   • Amount: ZMW {agreement.amount}\n"
        message += f"   • Created: {agreement.created_at.strftime('%Y-%m-%d')}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_outbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show agreements initiated by the user."""
    user_id = update.effective_user.id
    my_agreements = [
        agreement for agreement in agreements.values() 
        if agreement.initiator_id == user_id
    ]
    
    if not my_agreements:
        await update.message.reply_text("📭 Your outbox is empty. No agreements you've initiated.")
        return
    
    message = "📤 **Your Outbox**\n\nAgreements you've created:\n\n"
    for i, agreement in enumerate(my_agreements, 1):
        status_emoji = {
            'draft': '✏️',
            'pending_buyer': '⏳',
            'pending_witness': '👤',
            'completed': '✅',
            'paid': '💰'
        }.get(agreement.status, '❓')
        
        status_text = {
            'draft': 'Draft',
            'pending_buyer': 'Waiting for Buyer',
            'pending_witness': 'Waiting for Witness',
            'completed': 'Completed',
            'paid': 'Paid & Verified'
        }.get(agreement.status, 'Unknown')
        
        message += f"{i}. {status_emoji} **{agreement.title}**\n"
        message += f"   • Status: {status_text}\n"
        message += f"   • Amount: ZMW {agreement.amount}\n"
        message += f"   • Created: {agreement.created_at.strftime('%Y-%m-%d')}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_in_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show agreements in progress."""
    user_id = update.effective_user.id
    in_progress = [
        agreement for agreement in agreements.values() 
        if agreement.initiator_id == user_id and agreement.status in ['pending_buyer', 'pending_witness']
    ]
    
    if not in_progress:
        await update.message.reply_text("✅ No agreements currently in progress.")
        return
    
    message = "🔄 **In Progress**\n\nActive agreements:\n\n"
    for i, agreement in enumerate(in_progress, 1):
        message += f"{i}. **{agreement.title}**\n"
        message += f"   • Current Step: {get_current_step(agreement)}\n"
        message += f"   • Amount: ZMW {agreement.amount}\n"
        message += f"   • Created: {agreement.created_at.strftime('%Y-%m-%d')}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

def get_current_step(agreement):
    """Get human-readable current step."""
    steps = {
        'pending_buyer': 'Waiting for counterparty signature',
        'pending_witness': 'Waiting for witness signature'
    }
    return steps.get(agreement.status, 'Unknown step')

async def handle_agreement_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the step-by-step agreement creation process."""
    user_id = update.effective_user.id
    text = update.message.text
    
    step = context.user_data.get('agreement_step', '')
    
    if step == 'title':
        context.user_data['agreement_title'] = text
        context.user_data['agreement_step'] = 'seller_name'
        await update.message.reply_text(
            "Step 2 of 8: Enter your **Full Name** (as Seller/Initiator)"
        )
    
    elif step == 'seller_name':
        context.user_data['seller_name'] = text
        context.user_data['agreement_step'] = 'seller_nrc'
        await update.message.reply_text(
            "Step 3 of 8: Enter your **NRC Number**"
        )
    
    elif step == 'seller_nrc':
        context.user_data['seller_nrc'] = text
        context.user_data['agreement_step'] = 'seller_address'
        await update.message.reply_text(
            "Step 4 of 8: Enter your **Residential Address**"
        )
    
    elif step == 'seller_address':
        context.user_data['seller_address'] = text
        context.user_data['agreement_step'] = 'amount'
        await update.message.reply_text(
            "Step 5 of 8: Enter the **Amount** (in ZMW)\n"
            "Example: 5000.00"
        )
    
    elif step == 'amount':
        try:
            amount = float(text)
            context.user_data['amount'] = amount
            context.user_data['agreement_step'] = 'conditions'
            await update.message.reply_text(
                "Step 6 of 8: Enter the **Agreement Conditions/Description**\n\n"
                "Be specific about what is being agreed upon. Include all relevant details."
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a valid number (e.g., 5000.00)")
    
    elif step == 'conditions':
        context.user_data['conditions'] = text
        context.user_data['agreement_step'] = 'counterparty'
        
        # Create the agreement object
        agreement = Agreement(
            initiator_id=user_id,
            title=context.user_data['agreement_title'],
            amount=context.user_data['amount'],
            conditions=context.user_data['conditions'],
            seller_name=context.user_data['seller_name'],
            seller_nrc=context.user_data['seller_nrc'],
            seller_address=context.user_data['seller_address']
        )
        
        agreements[agreement.id] = agreement
        
        await update.message.reply_text(
            "Step 7 of 8: Enter the **Telegram username** of the counterparty (Buyer)\n"
            "Example: @john_doe\n\n"
            "Note: The counterparty must have a Telegram account and username set up."
        )
    
    elif step == 'counterparty':
        counterparty_username = text.strip('@')
        context.user_data['counterparty_username'] = counterparty_username
        
        # In a real app, we would search for the user here
        # For this prototype, we'll simulate finding the user
        counterparty_id = f"user_{counterparty_username}"
        
        agreement_id = list(agreements.keys())[-1]
        agreement = agreements[agreement_id]
        agreement.buyer_id = counterparty_id
        
        # Send notification to counterparty (simulated)
        notification_message = f"""
🔔 **New Agreement Request**

You have been invited to sign an agreement:

**Title:** {agreement.title}
**Amount:** ZMW {agreement.amount}
**Initiator:** {agreement.seller_name}

Tap the button below to review and sign this agreement.
"""
        
        keyboard = [[InlineKeyboardButton("📄 Review Agreement", callback_data=f"review_{agreement_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # In real app: send to counterparty
        # For now, just continue the process
        context.user_data['agreement_step'] = 'signature'
        
        await update.message.reply_text(
            "Step 8 of 8: **Digital Signature**\n\n"
            "Please sign below by drawing your signature. This will be your official digital signature for this agreement.\n\n"
            "*(Note: In the actual app, this would be a drawing interface. For this prototype, please type 'SIGN' to confirm your signature.)*"
        )
    
    elif step == 'signature':
        if text.upper() == 'SIGN':
            agreement_id = list(agreements.keys())[-1]
            agreement = agreements[agreement_id]
            agreement.seller_signature = "SIMULATED_SIGNATURE"
            agreement.status = "pending_buyer"
            
            await update.message.reply_text(
                "✅ **Agreement Created Successfully!**\n\n"
                f"Agreement ID: `{agreement.id}`\n"
                f"Title: **{agreement.title}**\n"
                f"Amount: ZMW {agreement.amount}\n\n"
                "The counterparty has been notified and will receive a message to review and sign this agreement.\n\n"
                "You can track the progress in your 'In Progress' section.",
                parse_mode='Markdown'
            )
            
            # Clear the user data
            context.user_data.clear()
        else:
            await update.message.reply_text(
                "Please type 'SIGN' to confirm your digital signature.\n"
                "*(This simulates the signature drawing interface that would be available in the actual app.)*"
            )

async def generate_agreement_document(agreement: Agreement):
    """
    Generate the final agreement document in the specified format.
    This would be a PDF in production, but we'll return the text format here.
    """
    document = f"""
SALE AND PURCHASE AGREEMENT
THIS AGREEMENT
This is an Agreement of Sale made on this {agreement.created_at.strftime('%d/%m/%Y at %H:%M:%S')}, between the following parties:

1. PARTIES
Seller
Full Name: {agreement.seller_name}
NRC Number: {agreement.seller_nrc}
Residential Address: {agreement.seller_address}

Buyer
Full Name: {agreement.buyer_name or '[Pending Signature]'}
NRC Number: {agreement.buyer_nrc or '[Pending Signature]'}
Residential Address: {agreement.buyer_address or '[Pending Signature]'}

Witness (Optional)
Full Name: {agreement.witness_name or '[Not Required]'}
NRC Number: {agreement.witness_nrc or '[Not Required]'}
Residential Address: {agreement.witness_address or '[Not Required]'}

2. AGREEMENT TITLE
{agreement.title}

3. DESCRIPTION OF ITEM / CONDITIONS
The Seller agrees to sell, and the Buyer agrees to purchase the item(s) under the terms below:
{agreement.conditions}

4. PURCHASE PRICE
Amount: ZMW {agreement.amount}

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
Seller Signature: {'[✓ Signed]' if agreement.seller_signature else '[Pending]'}
Buyer Signature: {'[✓ Signed]' if agreement.buyer_signature else '[Pending]'}
Witness Signature: {'[✓ Signed]' if agreement.witness_signature else '[Not Required]'}

9. VERIFICATION
This document was generated via ZamSign. Agreement ID: {agreement.id}
Scan QR code to verify authenticity.

---
ZamSign - Digital Agreements Made Simple.
Your Agreement. Digitally Secured.
"""
    return document

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and send a message to the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again or contact support."
        )

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add agreement creation handler
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^(📝 Initiate Agreement|📥 Inbox|📤 Outbox|🔄 In Progress)$'), 
        handle_message
    ))
    
    # Add step-by-step agreement handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(📝 Initiate Agreement|📥 Inbox|📤 Outbox|🔄 In Progress)$'),
        handle_agreement_creation
    ))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the Bot
    logger.info("Starting ZamSign Telegram Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
    