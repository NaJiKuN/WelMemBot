# x2.8
import sqlite3
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

# إعدادات البوت
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466
BOT_USERNAME = "@WelMemBot"

# إعداد قاعدة البيانات
def init_db():
    conn = sqlite3.connect('/home/ec2-user/projects/WelMemBot/bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (group_id TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# توليد كود عشوائي
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# التحقق من حالة المسؤول
def is_admin(user_id):
    return user_id == ADMIN_ID

# معالجة الأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = []

    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("إنشاء أكواد", callback_data='generate_codes')],
            [InlineKeyboardButton("عرض الأكواد", callback_data='show_codes')],
        ]
    else:
        keyboard = [[InlineKeyboardButton("إدخال كود", callback_data='enter_code')]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"مرحبًا! أنا {BOT_USERNAME}. اختر خيارًا من الأزرار أدناه:",
        reply_markup=reply_markup
    )

# معالجة استجابات الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'generate_codes' and is_admin(query.from_user.id):
        await query.message.reply_text("أدخل معرف المجموعة (مثال: -1002329495586):")
        context.user_data['state'] = 'awaiting_group_id'
    elif query.data == 'show_codes' and is_admin(query.from_user.id):
        await show_codes(query, context)
    elif query.data == 'enter_code':
        await query.message.reply_text("أدخل الكود:")
        context.user_data['state'] = 'awaiting_code'

# معالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')

    if state == 'awaiting_group_id' and is_admin(user_id):
        if text.startswith('-100'):
            context.user_data['group_id'] = text
            context.user_data['state'] = 'awaiting_code_count'
            await update.message.reply_text("أدخل عدد الأكواد المطلوبة:")
        else:
            await update.message.reply_text("معرف المجموعة غير صحيح. يجب أن يبدأ بـ -100. حاول مجددًا:")
    elif state == 'awaiting_code_count' and is_admin(user_id):
        try:
            count = int(text)
            if count <= 0:
                raise ValueError
            await generate_codes(update, context, count)
        except ValueError:
            await update.message.reply_text("أدخل رقمًا صحيحًا أكبر من 0:")
    elif state == 'awaiting_code':
        await validate_code(update, context, text)

# توليد الأكواد
async def generate_codes(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
    group_id = context.user_data.get('group_id')
    conn = sqlite3.connect('/home/ec2-user/projects/WelMemBot/bot.db')
    c = conn.cursor()

    # إضافة المجموعة إلى قاعدة البيانات إن لم تكن موجودة
    c.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", (group_id,))
    
    codes = []
    for _ in range(count):
        code = generate_code()
        c.execute("INSERT INTO codes (code, group_id, used) VALUES (?, ?, ?)", (code, group_id, 0))
        codes.append(code)
    
    conn.commit()
    conn.close()

    codes_text = "\n".join(codes)
    await update.message.reply_text(f"تم إنشاء {count} أكواد:\n{codes_text}")
    context.user_data['state'] = None

# عرض الأكواد
async def show_codes(query: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('/home/ec2-user/projects/WelMemBot/bot.db')
    c = conn.cursor()
    c.execute("SELECT code, group_id, used FROM codes")
    codes = c.fetchall()
    conn.close()

    if not codes:
        await query.message.reply_text("لا توجد أكواد مولدة.")
        return

    codes_text = "الأكواد المولدة:\n"
    for code, group_id, used in codes:
        status = "مستخدم" if used else "غير مستخدم"
        codes_text += f"كود: {code} | المجموعة: {group_id} | الحالة: {status}\n"

    await query.message.reply_text(codes_text)

# التحقق من الكود وإضافة العضو
async def validate_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    conn = sqlite3.connect('/home/ec2-user/projects/WelMemBot/bot.db')
    c = conn.cursor()
    c.execute("SELECT group_id, used FROM codes WHERE code = ?", (code,))
    result = c.fetchone()

    if result and not result[1]:
        group_id, _ = result
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name

        try:
            await context.bot.add_chat_members(group_id, user_id)
            c.execute("UPDATE codes SET used = 1 WHERE code = ?", (code,))
            conn.commit()

            welcome_message = (
                f"Hello and welcome, {username}!\n"
                "Your membership will automatically expire after one month.\n"
                "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
            )
            await context.bot.send_message(chat_id=group_id, text=welcome_message)
            await update.message.reply_text("تمت إضافتك إلى المجموعة بنجاح!")
        except TelegramError as e:
            await update.message.reply_text(f"خطأ: {e.message}")
    else:
        await update.message.reply_text("The entered code is invalid. Please try entering the code correctly.")
    
    conn.close()
    context.user_data['state'] = None

# معالجة الأعضاء الجدد
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        username = member.username or member.first_name
        welcome_message = (
            f"Hello and welcome, {username}!\n"
            "Your membership will automatically expire after one month.\n"
            "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
        )
        await update.message.reply_text(welcome_message)

# التشغيل الرئيسي
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    app.run_polling()

if __name__ == "__main__":
    main()
