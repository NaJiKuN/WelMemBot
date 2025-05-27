#!/usr/bin/env python3
# bot.py v4.3

import os
import json
import logging
from uuid import uuid4
from telegram import __version__ as TG_VER
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

# Configuration
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466
DATA_FILE = "/home/ec2-user/projects/WelMemBot/data.json"

# Conversation states
ADMIN_CHOICE, GET_GROUP_ID, GET_CODES_COUNT, SET_WELCOME_MSG = range(4)
USER_CODE_INPUT = 0

# Initialize logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_data():
    """Load data from JSON file"""
    if not os.path.exists(DATA_FILE):
        return {
            "groups": {},
            "codes": {},
            "welcome_messages": {}
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    """Save data to JSON file"""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin start handler"""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("إضافة مجموعة جديدة", callback_data="add_group")],
        [InlineKeyboardButton("عرض الأكواد", callback_data="show_codes")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "مرحبا أيها المسؤول! اختر الإجراء المطلوب:",
        reply_markup=reply_markup
    )
    return ADMIN_CHOICE

async def handle_admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin menu selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_group":
        await query.edit_message_text("أدخل معرف المجموعة (مثال: -1002329495586):")
        return GET_GROUP_ID
    elif query.data == "show_codes":
        return await show_codes_menu(query)

async def show_codes_menu(query):
    """Display codes statistics"""
    data = load_data()
    codes = data["codes"]
    
    active_codes = [k for k, v in codes.items() if not v["used"]]
    used_codes = [k for k, v in codes.items() if v["used"]]
    
    msg = (
        f"📊 إحصائيات الأكواد:\n"
        f"• الأكواد النشطة: {len(active_codes)}\n"
        f"• الأكواد المستخدمة: {len(used_codes)}\n\n"
        "اختر المجموعة لعرض أكوادها:"
    )
    
    groups = list(data["groups"].keys())
    keyboard = [[InlineKeyboardButton(g, callback_data=f"show_{g}")] for g in groups]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(msg, reply_markup=reply_markup)
    return ADMIN_CHOICE

async def generate_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate new codes"""
    data = load_data()
    group_id = context.user_data["group_id"]
    
    try:
        num_codes = int(update.message.text)
        if not 1 <= num_codes <= 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم بين 1 و 100")
        return GET_CODES_COUNT
    
    # Generate unique codes
    new_codes = [str(uuid4())[:8].upper() for _ in range(num_codes)]
    
    # Update data
    data["groups"][group_id] = {"active": True}
    for code in new_codes:
        data["codes"][code] = {
            "group_id": group_id,
            "used": False
        }
    save_data(data)
    
    # Create code buttons
    keyboard = [[InlineKeyboardButton(code, callback_data=f"copy_{code}")] for code in new_codes]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ تم توليد {num_codes} أكواد للمجموعة {group_id}:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User start handler"""
    await update.message.reply_text("🔑 الرجاء إرسال الكود الخاص بك:")
    return USER_CODE_INPUT

async def handle_user_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and process user code"""
    user = update.effective_user
    code = update.message.text.strip().upper()
    data = load_data()
    
    if code not in data["codes"]:
        await update.message.reply_text("The entered code is incorrect. Please try again.")
        return USER_CODE_INPUT
    
    code_data = data["codes"][code]
    
    if code_data["used"]:
        await update.message.reply_text("⚠️ هذا الكود مستخدم مسبقاً")
        return USER_CODE_INPUT
    
    group_id = code_data["group_id"]
    
    try:
        # Add user to group
        await context.bot.add_chat_member(
            chat_id=group_id,
            user_id=user.id
        )
        
        # Mark code as used
        data["codes"][code]["used"] = True
        save_data(data)
        
        # Send welcome message
        welcome_msg = data["welcome_messages"].get(
            group_id,
            "أهلاً وسهلاً بك، {username}!\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        ).format(username=user.full_name)
        
        await context.bot.send_message(
            chat_id=group_id,
            text=welcome_msg
        )
        
        await update.message.reply_text("🎉 تمت إضافتك إلى المجموعة بنجاح!")
        
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text("❌ فشلت الإضافة. يرجى التأكد من:")
    
    return ConversationHandler.END

async def set_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set custom welcome message"""
    data = load_data()
    group_id = " ".join(context.args)
    
    if not group_id.startswith("-100"):
        await update.message.reply_text("❌ معرف مجموعة غير صالح")
        return
    
    data["welcome_messages"][group_id] = update.message.text.split(" ", 1)[1]
    save_data(data)
    
    await update.message.reply_text(f"✅ تم تحديث الرسالة الترحيبية للمجموعة {group_id}")

def main():
    """Start the bot"""
    application = Application.builder().token(TOKEN).build()
    
    # Admin conversation handler
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("start", admin_start, filters=filters.User(ADMIN_ID))],
        states={
            ADMIN_CHOICE: [CallbackQueryHandler(handle_admin_choice)],
            GET_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: c.user_data.update({"group_id": u.message.text}) or u.message.reply_text("كم عدد الأكواد المطلوبة؟") or GET_CODES_COUNT)],
            GET_CODES_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_codes)]
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: u.message.reply_text("تم الإلغاء") or ConversationHandler.END)]
    )
    
    # User conversation handler
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", user_start)],
        states={
            USER_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_code)]
        },
        fallbacks=[]
    )
    
    # Add handlers
    application.add_handler(admin_conv)
    application.add_handler(user_conv)
    application.add_handler(CommandHandler("set_welcome", set_welcome_message, filters=filters.User(ADMIN_ID)))
    application.add_handler(CallbackQueryHandler(lambda u,c: u.answer("تم النسخ!") if "copy_" in u.data else None))
    
    application.run_polling()

if __name__ == "__main__":
    main()
