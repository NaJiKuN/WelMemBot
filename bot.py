# x1.4
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import string
import time
from datetime import datetime, timedelta
import os
import logging

# إعداد التسجيل (Logging)
logging.basicConfig(
    filename='/home/ec2-user/projects/WelMemBot/bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
bot = telebot.TeleBot(TOKEN)

# مسار قاعدة البيانات
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'

# إنشاء قاعدة البيانات إذا لم تكن موجودة
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS codes
                     (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS memberships
                     (user_id INTEGER, group_id TEXT, join_date TEXT, PRIMARY KEY (user_id, group_id))''')
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {str(e)}")

# التحقق من صلاحيات البوت
def check_bot_permissions(chat_id):
    try:
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        permissions = {
            'can_invite_users': bot_member.can_invite_users,
            'can_send_messages': bot_member.can_send_messages,
            'can_restrict_members': bot_member.can_restrict_members,
            'status': bot_member.status
        }
        logging.info(f"Bot permissions for chat {chat_id}: {permissions}")
        if bot_member.status not in ['administrator', 'creator']:
            logging.warning(f"Bot is not an admin in chat {chat_id}. Status: {bot_member.status}")
            return False
        if not bot_member.can_invite_users or not bot_member.can_send_messages or not bot_member.can_restrict_members:
            logging.warning(f"Insufficient permissions for chat {chat_id}: {permissions}")
            return False
        return True
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Telegram API error for chat {chat_id}: {str(e)}")
        if "chat not found" in str(e).lower():
            return False
        elif "bot is not a member" in str(e).lower():
            return False
        elif "blocked by user" in str(e).lower():
            return False
        raise  # إعادة إلقاء الاستثناءات الأخرى للتعامل معها لاحقًا
    except Exception as e:
        logging.error(f"Unexpected error checking permissions for chat {chat_id}: {str(e)}")
        return False

# توليد كود عشوائي
def generate_code(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# التحقق من إذا كان المستخدم هو الأدمن
def is_admin(user_id):
    return user_id == ADMIN_ID

# معالج عام لجميع الرسائل
@bot.message_handler(content_types=['text'])
def handle_all_messages(message):
    logging.info(f"Received message from user {message.from_user.id}: {message.text}")
    bot.reply_to(message, "تم استلام رسالتك. استخدم /start لبدء التفاعل مع البوت أو /check_permissions للتحقق من الصلاحيات.")

# معالجة الأمر /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    logging.info(f"Start command received from user {user_id}")
    if is_admin(user_id):
        bot.reply_to(message, "مرحبًا أيها الأدمن! أدخل ID المجموعة (مثال: -1002329495586):")
        bot.register_next_step_handler(message, get_group_id)
    else:
        bot.reply_to(message, "أدخل الكود الخاص بك:")
        bot.register_next_step_handler(message, check_code)

# أمر اختباري للتحقق من الصلاحيات
@bot.message_handler(commands=['check_permissions'])
def check_permissions(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /check_permissions by user {message.from_user.id}")
        return
    try:
        group_id = message.text.split()[1]
        if check_bot_permissions(group_id):
            bot.reply_to(message, f"البوت لديه الصلاحيات الكافية في المجموعة {group_id}.")
            logging.info(f"Permissions check passed for group {group_id}")
        else:
            bot.reply_to(message, f"البوت ليس لديه الصلاحيات الكافية في المجموعة {group_id}! تأكد من أن البوت مسؤول ويمكنه إضافة الأعضاء، إرسال الرسائل، وحظر الأعضاء.")
            logging.warning(f"Permissions check failed for group {group_id}")
    except IndexError:
        bot.reply_to(message, "يرجى إدخال معرف المجموعة بعد الأمر! مثال: /check_permissions -1002329495586")
        logging.warning(f"Missing group_id in /check_permissions command by user {message.from_user.id}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in /check_permissions for user {message.from_user.id}: {str(e)}")

# الحصول على ID المجموعة من الأدمن
def get_group_id(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return
    group_id = message.text.strip()
    logging.info(f"Received group_id: {group_id}")
    try:
        if not group_id.startswith('-100'):
            bot.reply_to(message, "ID المجموعة غير صالح! يجب أن يبدأ بـ -100.")
            logging.warning(f"Invalid group_id format: {group_id}")
            return
        if not check_bot_permissions(group_id):
            bot.reply_to(message, f"البوت ليس لديه الصلاحيات الكافية في المجموعة {group_id}! تأكد من أن البوت مسؤول ويمكنه إضافة الأعضاء، إرسال الرسائل، وحظر الأعضاء.")
            return
        bot.reply_to(message, f"تم تحديد المجموعة {group_id}. أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
    except telebot.apihelper.ApiTelegramException as e:
        if "chat not found" in str(e).lower():
            bot.reply_to(message, f"خطأ: المجموعة {group_id} غير موجودة أو البوت ليس عضوًا فيها.")
        elif "bot is not a member" in str(e).lower():
            bot.reply_to(message, f"خطأ: البوت ليس عضوًا في المجموعة {group_id}. أضف البوت إلى المجموعة أولاً.")
        else:
            bot.reply_to(message, f"خطأ في API تيليجرام: {str(e)}")
        logging.error(f"Telegram API error in get_group_id for chat {group_id}: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}. تأكد من إدخال ID المجموعة بشكل صحيح.")
        logging.error(f"Error in get_group_id: {str(e)}")

# توليد الأكواد
def generate_codes(message, group_id):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
            logging.warning(f"Invalid number of codes: {message.text}")
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
        logging.info(f"Generated {num_codes} codes for group {group_id}")
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
        logging.warning(f"Invalid input for number of codes: {message.text}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in generate_codes: {str(e)}")

# التحقق من الكود المدخل من المستخدم
def check_code(message):
    code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logging.info(f"Checking code {code} for user {user_id}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, used FROM codes WHERE code = ?", (code,))
    result = c.fetchone()
    if result and result[1] == 0:
        group_id = result[0]
        try:
            if not check_bot_permissions(group_id):
                bot.reply_to(message, f"البوت ليس لديه الصلاحيات الكافية في المجموعة {group_id}! تأكد من أن البوت مسؤول ويمكنه إضافة الأعضاء، إرسال الرسائل، وحظر الأعضاء.")
                logging.warning(f"Insufficient permissions for group {group_id}")
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
            logging.info(f"User {user_id} added to group {group_id} with code {code}")
        except telebot.apihelper.ApiTelegramException as e:
            bot.reply_to(message, f"خطأ في API تيليجرام: {str(e)}")
            logging.error(f"Telegram API error adding user {user_id} to group {group_id}: {str(e)}")
        except Exception as e:
            bot.reply_to(message, f"خطأ: {str(e)}")
            logging.error(f"Error adding user {user_id} to group {group_id}: {str(e)}")
    else:
        bot.reply_to(message, "The entered code is invalid. Please try entering the code correctly.")
        logging.warning(f"Invalid or used code {code} by user {user_id}")
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
                    logging.info(f"User {user_id} removed from group {group_id} due to membership expiration")
                except Exception as e:
                    logging.error(f"Error kicking user {user_id} from group {group_id}: {str(e)}")
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error in membership check: {str(e)}")
        time.sleep(86400)  # التحقق كل 24 ساعة

# أمر اختباري لإضافة عضو يدويًا
@bot.message_handler(commands=['test_add'])
def test_add(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /test_add by user {message.from_user.id}")
        return
    try:
        group_id = message.text.split()[1]
        if not check_bot_permissions(group_id):
            bot.reply_to(message, f"البوت ليس لديه الصلاحيات الكافية في المجموعة {group_id}! تأكد من أن البوت مسؤول ويمكنه إضافة الأعضاء، إرسال الرسائل، وحظر الأعضاء.")
            logging.warning(f"Insufficient permissions for group {group_id} in /test_add")
            return
        bot.add_chat_member(group_id, message.from_user.id)
        bot.reply_to(message, "تمت الإضافة بنجاح!")
        logging.info(f"User {message.from_user.id} successfully added to group {group_id} via /test_add")
    except IndexError:
        bot.reply_to(message, "يرجى إدخال معرف المجموعة بعد الأمر! مثال: /test_add -1002329495586")
        logging.warning(f"Missing group_id in /test_add command by user {message.from_user.id}")
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"خطأ في API تيليجرام: {str(e)}")
        logging.error(f"Telegram API error in /test_add for user {message.from_user.id}: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in /test_add for user {message.from_user.id}: {str(e)}")

# بدء البوت
if __name__ == '__main__':
    init_db()
    import threading
    threading.Thread(target=check_memberships, daemon=True).start()
    logging.info("Bot started polling")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logging.error(f"Error in bot polling: {str(e)}")
            time.sleep(10)  # إعادة المحاولة بعد 10 ثوانٍ
