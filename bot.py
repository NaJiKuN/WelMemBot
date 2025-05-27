#!/usr/bin/env python3
# bot.py v4.1

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
GET_GROUP_ID, GET_CODES_COUNT = range(2)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start"""
    user = update.effective_user
    
    if user.id == ADMIN_ID:
        # وضع المسؤول
        await update.message.reply_text(
            "مرحبا أيها المسؤول!\n"
            "الرجاء إدخال معرف المجموعة (مثال: -1002329495586):"
        )
        return GET_GROUP_ID
    else:
        # وضع المستخدم العادي
        await update.message.reply_text(
            "مرحبا! الرجاء إدخال الكود الخاص بك:"
        )
        return GET_GROUP_ID

async def get_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على معرف المجموعة من المسؤول"""
    group_id = update.message.text
    context.user_data["group_id"] = group_id
    await update.message.reply_text("كم عدد الأكواد التي تريد توليدها؟")
    return GET_CODES_COUNT

async def generate_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توليد الأكواد وحفظها"""
    data = load_data()
    num_codes = int(update.message.text)
    group_id = context.user_data["group_id"]
    
    # توليد الأكواد
    codes = [str(uuid4())[:8] for _ in range(num_codes)]
    
    # حفظ البيانات
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
        f"تم توليد {num_codes} أكواد للمجموعة {group_id}:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأكواد من المستخدمين"""
    user = update.effective_user
    code = update.message.text.upper()
    data = load_data()
    
    if code in data["codes"] and not data["codes"][code]["used"]:
        group_id = data["codes"][code]["group_id"]
        
        # إضافة المستخدم إلى المجموعة
        try:
            await context.bot.add_chat_member(
                chat_id=group_id,
                user_id=user.id,
            )
            # تحديث حالة الكود
            data["codes"][code]["used"] = True
            save_data(data)
            
            # إرسال رسالة الترحيب
            welcome_msg = (
                f"أهلاً وسهلاً بك، {user.full_name}!\n"
                "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
                "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
            )
            await context.bot.send_message(
                chat_id=group_id,
                text=welcome_msg
            )
            await update.message.reply_text("تمت إضافتك إلى المجموعة بنجاح!")
        except Exception as e:
            await update.message.reply_text("حدث خطأ أثناء الإضافة إلى المجموعة")
    else:
        await update.message.reply_text("The entered code is incorrect. Please try again.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text("تم الإلغاء")
    return ConversationHandler.END

async def copy_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخ الكود عند النقر على الزر"""
    query = update.callback_query
    code = query.data.split("_")[1]
    await query.answer(f"تم نسخ الكود: {code}")

def main():
    """تشغيل البوت"""
    application = Application.builder().token(TOKEN).build()
    
    # محادثة المسؤول
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_id)],
            GET_CODES_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_codes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    
    # معالجة الأكواد من المستخدمين
    user_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code)
    
    # معالجة أحداث الأزرار
    application.add_handler(CallbackQueryHandler(copy_code, pattern="^copy_"))
    
    application.add_handler(admin_conv)
    application.add_handler(user_handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()
