# x1.0
import json
import uuid
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import TelegramError

# إعدادات البوت
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466
GROUP_ID = "-1002329495586"
DATA_FILE = "/home/ec2-user/projects/WelMemBot/codes.json"

# حالات المحادثة
ASK_GROUP_ID, ASK_CODE_COUNT, ASK_CODE = range(3)

# تحميل الأكواد من ملف JSON
def load_codes():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# حفظ الأكواد إلى ملف JSON
def save_codes(codes):
    with open(DATA_FILE, "w") as f:
        json.dump(codes, f, indent=4)

# أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the invitation code:")
    return ASK_CODE

# التحقق من الكود وإضافة المستخدم
async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_code = update.message.text
    codes = load_codes()

    if user_code in codes and not codes[user_code]["used"]:
        group_id = codes[user_code]["group_id"]
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name

        try:
            # إضافة المستخدم إلى المجموعة
            await context.bot.add_chat_member(chat_id=group_id, user_id=user_id)
            # إرسال رسالة ترحيبية
            welcome_message = (
                f"Welcome, {username}!\n"
                "Your membership will automatically expire after one month.\n"
                "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
            )
            await context.bot.send_message(chat_id=group_id, text=welcome_message)
            # تحديث حالة الكود إلى مستخدم
            codes[user_code]["used"] = True
            save_codes(codes)
            await update.message.reply_text("You have been added to the group successfully!")
        except TelegramError as e:
            await update.message.reply_text(f"Error adding you to the group: {str(e)}")
    else:
        await update.message.reply_text("The entered code is incorrect. Please try entering the code correctly.")
    
    return ConversationHandler.END

# أمر توليد الأكواد (للمسؤول فقط)
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return ConversationHandler.END

    await update.message.reply_text("Please enter the group ID (e.g., -1002329495586):")
    return ASK_GROUP_ID

# استقبال GROUP_ID
async def receive_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["group_id"] = update.message.text
    await update.message.reply_text("How many codes do you want to generate?")
    return ASK_CODE_COUNT

# استقبال عدد الأكواد وتوليدها
async def receive_code_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("Please enter a valid number greater than 0.")
            return ASK_CODE_COUNT

        group_id = context.user_data.get("group_id", GROUP_ID)
        codes = load_codes()

        # توليد الأكواد
        new_codes = []
        for _ in range(count):
            code = str(uuid.uuid4())[:8]  # توليد كود قصير فريد
            codes[code] = {"group_id": group_id, "used": False}
            new_codes.append(code)

        save_codes(codes)
        await update.message.reply_text(f"Generated codes:\n{', '.join(new_codes)}")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return ASK_CODE_COUNT

# إلغاء المحادثة
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

def main():
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()

    # إعداد ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("generate", generate),
        ],
        states={
            ASK_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_group_id)],
            ASK_CODE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code_count)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # إضافة المعالج
    application.add_handler(conv_handler)

    # تشغيل البوت
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
