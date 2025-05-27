#!/usr/bin/env python3
# bot.py v4.2

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

# تهيئة الإعدادات
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466
DATA_FILE = "/home/ec2-user/projects/WelMemBot/data.json"

# حالات المحادثة
ADMIN_GET_GROUP_ID, ADMIN_GET_COUNT = range(2)
USER_AWAIT_CODE = 2

# تهيئة التسجيل
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_data():
    """تحميل البيانات من الملف"""
    if not os.path.exists(DATA_FILE):
        return {"groups": {}, "codes": {}}
    
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    """حفظ البيانات في الملف"""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء محادثة المسؤول"""
    await update.message.reply_text(
        "مرحبا أيها المسؤول!\n"
        "الرجاء إدخال معرف المجموعة (مثال: -1002329495586):"
    )
    return ADMIN_GET_GROUP_ID

async def get_admin_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على معرف المجموعة من المسؤول"""
    group_id = update.message.text.strip()
    context.user_data["group_id"] = group_id
    await update.message.reply_text("كم عدد الأكواد التي تريد توليدها؟")
    return ADMIN_GET_COUNT

async def generate_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توليد الأكواد للمجموعة"""
    data = load_data()
    group_id = context.user_data["group_id"]
    
    try:
        num_codes = int(update.message.text)
        if num_codes < 1 or num_codes > 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم بين 1 و 100")
        return ADMIN_GET_COUNT
    
    # توليد الأكواد
    codes = [str(uuid4())[:8].upper() for _ in range(num_codes)]
    
    # تحديث البيانات
    data["groups"][group_id] = {"active": True}
    for code in codes:
        data["codes"][code] = {
            "group_id": group_id,
            "used": False
        }
    save_data(data)
    
    # إنشاء أزرار للأكواد
    keyboard = [
        [InlineKeyboardButton(code, callback_data=f"copy_{code}")]
        for code in codes
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ تم توليد {num_codes} أكواد للمجموعة:\n{group_id}",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء محادثة المستخدم"""
    await update.message.reply_text("🔑 الرجاء إدخال الكود الخاص بك:")
    return USER_AWAIT_CODE

async def handle_user_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كود المستخدم"""
    user = update.effective_user
    code = update.message.text.strip().upper()
    data = load_data()
    
    # حالة الكود غير موجود
    if code not in data["codes"]:
        await update.message.reply_text("The entered code is incorrect. Please try again.")
        return USER_AWAIT_CODE
    
    code_data = data["codes"][code]
    
    # حالة الكود مستخدم مسبقاً
    if code_data["used"]:
        await update.message.reply_text("⚠️ هذا الكود مستخدم مسبقاً")
        return USER_AWAIT_CODE
    
    group_id = code_data["group_id"]
    
    # التحقق من وجود المجموعة
    if group_id not in data["groups"] or not data["groups"][group_id]["active"]:
        await update.message.reply_text("❌ المجموعة المحددة غير نشطة")
        return ConversationHandler.END
    
    try:
        # محاولة إضافة المستخدم
        await context.bot.add_chat_member(
            chat_id=group_id,
            user_id=user.id
        )
        
        # تحديث حالة الكود
        data["codes"][code]["used"] = True
        save_data(data)
        
        # إرسال رسالة الترحيب في المجموعة
        welcome_msg = (
            f"أهلاً وسهلاً بك، {user.full_name}!\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        )
        await context.bot.send_message(
            chat_id=group_id,
            text=welcome_msg
        )
        
        await update.message.reply_text("🎉 تمت إضافتك إلى المجموعة بنجاح!")
        
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء الإضافة. يرجى التأكد من:\n"
                                      "- وجودي كمسؤول في المجموعة\n"
                                      "- عدم مغادرتك السابقة للمجموعة")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    await update.message.reply_text("تم الإلغاء")
    return ConversationHandler.END

async def copy_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخ الكود عند النقر على الزر"""
    query = update.callback_query
    code = query.data.split("_")[1]
    await query.answer(f"تم النسخ: {code}")

def main():
    """تشغيل البوت"""
    application = Application.builder().token(TOKEN).build()
    
    # محادثة المسؤول
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("start", admin_start, filters=filters.User(ADMIN_ID))],
        states={
            ADMIN_GET_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_admin_group)],
            ADMIN_GET_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_codes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    
    # محادثة المستخدم
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", user_start)],
        states={
            USER_AWAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    
    # معالجة أحداث الأزرار
    application.add_handler(CallbackQueryHandler(copy_code, pattern="^copy_"))
    
    application.add_handler(admin_conv)
    application.add_handler(user_conv)
    
    application.run_polling()

if __name__ == "__main__":
    main()
