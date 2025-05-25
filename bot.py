# x1.2
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import string
import time
from datetime import datetime, timedelta
import os

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
bot = telebot.TeleBot(TOKEN)

# مسار قاعدة البيانات
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'

# إنشاء قاعدة البيانات إذا لم تكن موجودة
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS codes
                 (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS memberships
                 (user_id INTEGER, group_id TEXT, join_date TEXT, PRIMARY KEY (user_id, group_id))''')
    conn.commit()
    conn.close()

# التحقق من صلاحيات البوت
def check_bot_permissions(chat_id):
    try:
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        if not bot_member.can_invite_users or not bot_member.can_send_messages:
            return False
        return True
    except Exception as e:
        print(f"Error checking permissions: {e}")
        return False

# توليد كود عشوائي
def generate_code(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# التحقق من إذا كان المستخدم هو الأدمن
def is_admin(user_id):
    return user_id == ADMIN_ID

# معالجة الأمر /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        bot.reply_to(message, "مرحبًا أيها الأدمن! أدخل ID المجموعة (مثال: -1002329495586):")
        bot.register_next_step_handler(message, get_group_id)
    else:
        bot.reply_to(message, "أدخل الكود الخاص بك:")
        bot.register_next_step_handler(message, check_code)

# الحصول على ID المجموعة من الأدمن
def get_group_id(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    group_id = message.text.strip()
    try:
        if not group_id.startswith('-100'):
            bot.reply_to(message, "ID المجموعة غير صالح! يجب أن يبدأ بـ -100.")
            return
        if not check_bot_permissions(group_id):
            bot.reply_to(message, "البوت ليس لديه الصلاحيات الكافية في المجموعة! تأكد من أن البوت يمكنه إضافة الأعضاء وإرسال الرسائل.")
            return
        bot.reply_to(message, f"تم تحديد المجموعة {group_id}. أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
    except Exception as e:
        bot.reply_to(message, f"خطأ: {e}. تأكد من إدخال ID المجموعة بشكل صحيح.")

# توليد الأكواد
def generate_codes(message, group_id):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        codes = []
        for _ in range(num_codes):
            code = generate_code()
            c.execute("INSERT INTO codes (code, group_id, used) VALUES (?, ?, 0)", (code, group_id))
            codes.append(code)
        conn.commit()
        conn.close()
        codes_str = "\n".join(codes)
        bot.reply_to(message, f"تم توليد الأكواد التالية:\n{codes_str}")
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {e}")

# التحقق من الكود المدخل من المستخدم
def check_code(message):
    code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, used FROM codes WHERE code = ?", (code,))
    result = c.fetchone()
    if result and result[1] == 0:
        group_id = result[0]
        try:
            if not check_bot_permissions(group_id):
                bot.reply_to(message, "البوت ليس لديه الصلاحيات الكافية في المجموعة!")
                return
            bot.add_chat_member(group_id, user_id)
            c.execute("UPDATE codes SET used = 1 WHERE code = ?", (code,))
            c.execute("INSERT INTO memberships (user_id, group_id, join_date) VALUES (?, ?, ?)",
                      (user_id, group_id, datetime.now().isoformat()))
            conn.commit()
            welcome_message = (
                f"Welcome, {username}!\n"
                "Your membership will automatically expire after one month.\n"
                "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
            )
            bot.send_message(group_id, welcome_message)
            bot.reply_to(message, "تمت إضافتك إلى المجموعة بنجاح!")
        except Exception as e:
            bot.reply_to(message, f"خطأ: {e}")
    else:
        bot.reply_to(message, "The entered code is invalid. Please try entering the code correctly.")
    conn.close()

# إنهاء العضوية بعد شهر
def check_memberships():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            one_month_ago = (datetime.now() - timedelta(days=30)).isoformat()
            c.execute("SELECT user_id, group_id FROM memberships WHERE join_date < ?", (one_month_ago,))
            expired = c.fetchall()
            for user_id, group_id in expired:
                try:
                    bot.kick_chat_member(group_id, user_id)
                    c.execute("DELETE FROM memberships WHERE user_id = ? AND group_id = ?", (user_id, group_id))
                except Exception as e:
                    print(f"Error kicking user {user_id} from group {group_id}: {e}")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error in membership check: {e}")
        time.sleep(86400)  # التحقق كل 24 ساعة

# بدء البوت
if __name__ == '__main__':
    init_db()
    import threading
    threading.Thread(target=check_memberships, daemon=True).start()
    bot.polling(none_stop=True)
