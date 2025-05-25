# x1.6
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
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'

bot = telebot.TeleBot(TOKEN)

class DatabaseManager:
    """فئة لإدارة عمليات قاعدة البيانات"""
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """تهيئة قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS codes
                            (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER DEFAULT 0, invite_link TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS memberships
                            (user_id INTEGER, group_id TEXT, join_date TEXT, PRIMARY KEY (user_id, group_id))''')
                c.execute('''CREATE TABLE IF NOT EXISTS groups
                            (group_id TEXT PRIMARY KEY, welcome_message TEXT, is_private INTEGER DEFAULT 0)''')
                conn.commit()
            logging.info("Database initialized successfully.")
        except Exception as e:
            logging.error(f"Error initializing database: {str(e)}")
    
    def execute_query(self, query, params=(), fetch=False):
        """تنفيذ استعلام على قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(query, params)
                if fetch:
                    return c.fetchall()
                conn.commit()
        except Exception as e:
            logging.error(f"Database error: {str(e)}")
            raise

class BotPermissions:
    """فئة للتحقق من صلاحيات البوت"""
    @staticmethod
    def check_bot_permissions(bot_instance, chat_id):
        """التحقق من صلاحيات البوت في المجموعة"""
        try:
            chat = bot_instance.get_chat(chat_id)
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            permissions = {
                'status': bot_member.status,
                'can_invite_users': bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else False,
                'can_send_messages': bot_member.can_send_messages if hasattr(bot_member, 'can_send_messages') else False,
                'can_restrict_members': bot_member.can_restrict_members if hasattr(bot_member, 'can_restrict_members') else False,
                'chat_type': chat.type
            }
            logging.info(f"Bot permissions for chat {chat_id}: {permissions}")
            if bot_member.status not in ['administrator', 'creator']:
                return False, "البوت ليس مسؤولًا في المجموعة."
            if not all([permissions['can_invite_users'], permissions['can_send_messages'], permissions['can_restrict_members']]):
                return False, "البوت ليس لديه الصلاحيات الكافية (إضافة أعضاء، إرسال رسائل، حظر أعضاء)."
            return True, "الصلاحيات صحيحة."
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Telegram API error for chat {chat_id}: {str(e)}")
            if "chat not found" in str(e).lower():
                return False, "المجموعة غير موجودة أو معرف المجموعة غير صحيح."
            elif "bot is not a member" in str(e).lower():
                return False, "البوت ليس عضوًا في المجموعة. أضف البوت إلى المجموعة أولاً."
            return False, f"خطأ في API تيليجرام: {str(e)}"
        except Exception as e:
            logging.error(f"Unexpected error checking permissions for chat {chat_id}: {str(e)}")
            return False, f"خطأ غير متوقع: {str(e)}"

class CodeGenerator:
    """فئة لتوليد وإدارة الأكواد"""
    @staticmethod
    def generate_code(length=8):
        """توليد كود عشوائي"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_multiple_codes(bot_instance, db_manager, group_id, count):
        """توليد عدة أكواد مع روابط دعوة للمجموعة"""
        codes = []
        for _ in range(count):
            code = CodeGenerator.generate_code()
            # توليد رابط دعوة لشخص واحد
            try:
                success, msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
                if not success:
                    raise Exception(msg)
                invite_link = bot_instance.create_chat_invite_link(
                    group_id,
                    member_limit=1,
                    expire_date=int(time.time()) + 86400  # ينتهي بعد 24 ساعة
                ).invite_link
                db_manager.execute_query(
                    "INSERT INTO codes (code, group_id, used, invite_link) VALUES (?, ?, 0, ?)",
                    (code, group_id, invite_link)
                )
                codes.append((code, invite_link))
            except Exception as e:
                logging.error(f"Failed to generate invite link for code {code}: {str(e)}")
                continue
        return codes

class MembershipManager:
    """فئة لإدارة العضويات"""
    @staticmethod
    def add_member(bot_instance, db_manager, user_id, group_id, code):
        """إضافة عضو جديد إلى المجموعة باستخدام رابط الدعوة"""
        try:
            # التحقق من وجود الكود ورابط الدعوة
            result = db_manager.execute_query(
                "SELECT invite_link FROM codes WHERE code = ? AND group_id = ? AND used = 0",
                (code, group_id),
                fetch=True
            )
            if not result:
                return False, "الكود غير صالح أو مستخدم من قبل."
            
            invite_link = result[0][0]
            # إرسال رابط الدعوة للمستخدم
            bot_instance.send_message(user_id, f"انضم إلى المجموعة باستخدام هذا الرابط: {invite_link}")
            
            # تحديث قاعدة البيانات (لكن لا نحدد الكود كمستخدم حتى ينضم فعليًا عبر الرابط)
            return True, "تم إرسال رابط الدعوة. يرجى استخدامه للانضمام إلى المجموعة!"
        except telebot.apihelper.ApiTelegramException as e:
            error_msg = f"خطأ في API تيليجرام: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"خطأ: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
    
    @staticmethod
    def get_welcome_message(db_manager, group_id):
        """الحصول على رسالة الترحيب للمجموعة"""
        result = db_manager.execute_query(
            "SELECT welcome_message FROM groups WHERE group_id = ?",
            (group_id,),
            fetch=True
        )
        return result[0][0] if result and result[0][0] else "مرحبًا بك في المجموعة! يرجى الالتزام بالقواعد."

# تهيئة مدير قاعدة البيانات
db_manager = DatabaseManager(DB_PATH)

# ===== معالجات الأوامر =====

@bot.message_handler(commands=['start', 'help'])
def start(message):
    """معالجة أمر /start"""
    user_id = message.from_user.id
    logging.info(f"Start command from user {user_id}")
    
    if user_id == ADMIN_ID:
        bot.reply_to(message, "مرحبًا أيها الأدمن! أدخل معرف المجموعة (يمكنك الحصول عليه بإرسال /id في المجموعة):")
        bot.register_next_step_handler(message, get_group_id)
    else:
        bot.reply_to(message, "أدخل الكود الخاص بك للانضمام إلى المجموعة:")
        bot.register_next_step_handler(message, check_code)

@bot.message_handler(commands=['id'])
def get_group_id_command(message):
    """الحصول على معرف المجموعة"""
    if message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, f"معرف هذه المجموعة هو: {message.chat.id}\nيمكنك استخدامه لإعداد البوت.")
    else:
        bot.reply_to(message, "هذا الأمر يعمل فقط داخل المجموعات.")

@bot.message_handler(commands=['check_permissions'])
def check_permissions(message):
    """التحقق من صلاحيات البوت"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /check_permissions by user {message.from_user.id}")
        return
    try:
        group_id = message.text.split()[1]
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        bot.reply_to(message, msg)
        logging.info(f"Permissions check for group {group_id}: {msg}")
    except IndexError:
        bot.reply_to(message, "يرجى إدخال معرف المجموعة! مثال: /check_permissions -1002329495586")
        logging.warning(f"Missing group_id in /check_permissions by user {message.from_user.id}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in /check_permissions: {str(e)}")

@bot.message_handler(commands=['status'])
def status(message):
    """عرض حالة البوت في المجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /status by user {message.from_user.id}")
        return
    try:
        group_id = message.text.split()[1]
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        if success:
            bot.reply_to(message, f"البوت يعمل بشكل صحيح في المجموعة {group_id}:\n{msg}")
        else:
            bot.reply_to(message, f"مشكلة في المجموعة {group_id}:\n{msg}")
        logging.info(f"Status check for group {group_id}: {msg}")
    except IndexError:
        bot.reply_to(message, "يرجى إدخال معرف المجموعة! مثال: /status -1002329495586")
        logging.warning(f"Missing group_id in /status by user {message.from_user.id}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in /status: {str(e)}")

@bot.message_handler(commands=['revoke_invite'])
def revoke_invite(message):
    """إلغاء رابط دعوة مرتبط بكود"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /revoke_invite by user {message.from_user.id}")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "يرجى إدخال الكود! مثال: /revoke_invite ABC12345")
            return
        code = parts[1]
        result = db_manager.execute_query(
            "SELECT group_id, invite_link FROM codes WHERE code = ? AND used = 0",
            (code,),
            fetch=True
        )
        if not result:
            bot.reply_to(message, "الكود غير صالح أو مستخدم من قبل.")
            return
        group_id, invite_link = result[0]
        bot.revoke_chat_invite_link(group_id, invite_link)
        db_manager.execute_query("UPDATE codes SET invite_link = NULL WHERE code = ?", (code,))
        bot.reply_to(message, f"تم إلغاء رابط الدعوة المرتبط بالكود {code}.")
        logging.info(f"Revoked invite link for code {code} in group {group_id}")
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"خطأ في API تيليجرام: {str(e)}")
        logging.error(f"Error in /revoke_invite: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in /revoke_invite: {str(e)}")

def get_group_id(message):
    """الحصول على معرف المجموعة من الأدمن"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return
    
    group_id = message.text.strip()
    logging.info(f"Admin entered group_id: {group_id}")
    
    try:
        if not group_id.startswith('-100'):
            bot.reply_to(message, "معرف المجموعة غير صالح! يجب أن يبدأ بـ -100.")
            logging.warning(f"Invalid group_id format: {group_id}")
            return
        
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        if not success:
            bot.reply_to(message, f"خطأ: {msg}\nتأكد من:\n1. أن البوت عضو في المجموعة\n2. أن لديه صلاحيات إضافة أعضاء، إرسال رسائل، وحظر أعضاء\n3. استخدم /id داخل المجموعة للحصول على المعرف الصحيح.")
            return
        
        chat = bot.get_chat(group_id)
        is_private = chat.type in ['group', 'supergroup']
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, f"مرحبًا بك في {chat.title}! يرجى الالتزام بالقواعد.", int(is_private))
        )
        
        bot.reply_to(message, f"تم تحديد المجموعة {chat.title} (ID: {group_id}). أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
        
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nتأكد من:\n1. أن البوت عضو في المجموعة\n2. أنك أدخلت المعرف بشكل صحيح\n3. استخدم /id داخل المجموعة للحصول على المعرف الصحيح")
        logging.error(f"Telegram API error in get_group_id: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"خطأ غير متوقع: {str(e)}")
        logging.error(f"Error in get_group_id: {str(e)}")

def generate_codes(message, group_id):
    """توليد الأكواد مع روابط الدعوة للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return
    
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
            logging.warning(f"Invalid number of codes: {message.text}")
            return
        
        codes = CodeGenerator.generate_multiple_codes(bot, db_manager, group_id, num_codes)
        if not codes:
            bot.reply_to(message, "فشل في توليد الأكواد. تحقق من صلاحيات البوت في المجموعة.")
            return
        codes_str = "\n".join([f"🎟 الكود: {code}\n📎 الرابط: {link}" for code, link in codes])
        bot.reply_to(message, f"تم توليد الأكواد التالية:\n{codes_str}\n\nيمكنك مشاركة هذه الأكواد مع الأعضاء للانضمام إلى المجموعة.")
        logging.info(f"Generated {num_codes} codes for group {group_id}")
        
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
        logging.warning(f"Invalid input for number of codes: {message.text}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error generating codes: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"User {user_id} entered code: {code}")
    
    result = db_manager.execute_query(
        "SELECT group_id FROM codes WHERE code = ? AND used = 0",
        (code,),
        fetch=True
    )
    
    if not result:
        bot.reply_to(message, "الكود غير صالح أو مستخدم من قبل! يرجى التأكد من الكود والمحاولة مرة أخرى.")
        logging.warning(f"Invalid or used code {code} by user {user_id}")
        return
    
    group_id = result[0][0]
    success, msg = MembershipManager.add_member(bot, db_manager, user_id, group_id, code)
    bot.reply_to(message, msg)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    """معالجة الرسائل النصية غير الأوامر"""
    logging.info(f"Received text message from user {message.from_user.id}: {message.text}")
    bot.reply_to(message, "يرجى استخدام /start لبدء التفاعل مع البوت.")

@bot.message_handler(commands=['set_welcome'])
def set_welcome(message):
    """تعيين رسالة ترحيب مخصصة للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        logging.warning(f"Unauthorized access attempt for /set_welcome by user {message.from_user.id}")
        return
    
    try:
        if message.chat.type in ['group', 'supergroup']:
            group_id = str(message.chat.id)
            welcome_msg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        else:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                bot.reply_to(message, "يرجى إدخال معرف المجموعة ورسالة الترحيب! مثال: /set_welcome -1002329495586 مرحبًا بك!")
                return
            group_id, welcome_msg = parts[1], parts[2]
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, welcome_msg, int(bot.get_chat(group_id).type in ['group', 'supergroup']))
        )
        bot.reply_to(message, f"تم تحديث رسالة الترحيب للمجموعة {group_id}!")
        logging.info(f"Updated welcome message for group {group_id}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nاستخدم:\n- داخل المجموعة: /set_welcome <رسالة الترحيب>\n- خارج المجموعة: /set_welcome <group_id> <رسالة الترحيب>")
        logging.error(f"Error in /set_welcome: {str(e)}")

# معالج انضمام الأعضاء الجدد
@bot.chat_member_handler()
def handle_chat_member_update(chat_member_updated):
    """معالجة انضمام الأعضاء الجدد إلى المجموعة"""
    new_status = chat_member_updated.new_chat_member.status
    if new_status == "member":
        user = chat_member_updated.new_chat_member.user
        group_id = str(chat_member_updated.chat.id)
        user_id = user.id
        username = user.first_name or user.username or f"User_{user_id}"
        logging.info(f"New member {user_id} ({username}) joined group {group_id}")
        
        # تحديث قاعدة البيانات للكود المستخدم (إذا انضم عبر رابط دعوة)
        result = db_manager.execute_query(
            "SELECT code FROM codes WHERE invite_link LIKE ? AND group_id = ? AND used = 0",
            (f"%{chat_member_updated.invite_link}%", group_id),
            fetch=True
        )
        if result:
            code = result[0][0]
            db_manager.execute_query("UPDATE codes SET used = 1 WHERE code = ?", (code,))
            db_manager.execute_query(
                "INSERT INTO memberships (user_id, group_id, join_date) VALUES (?, ?, ?)",
                (user_id, group_id, datetime.now().isoformat())
            )
            logging.info(f"Code {code} marked as used for user {user_id} in group {group_id}")
        
        # إرسال رسالة الترحيب باللغة الإنجليزية
        welcome_msg = (
            f"Welcome, {username}!\n"
            "Your membership will automatically expire after one month.\n"
            "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
        )
        bot.send_message(group_id, welcome_msg)

# ===== الوظائف الخلفية =====

def check_expired_memberships():
    """فحص العضويات المنتهية الصلاحية"""
    while True:
        try:
            expired = db_manager.execute_query(
                "SELECT user_id, group_id FROM memberships WHERE join_date < ?",
                ((datetime.now() - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for user_id, group_id in expired:
                try:
                    bot.kick_chat_member(group_id, user_id)
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (user_id, group_id)
                    )
                    logging.info(f"User {user_id} removed from group {group_id}")
                except Exception as e:
                    logging.error(f"Error removing user {user_id} from group {group_id}: {str(e)}")
        except Exception as e:
            logging.error(f"Error in membership check: {str(e)}")
        time.sleep(86400)  # التحقق كل 24 ساعة

# بدء البوت
if __name__ == '__main__':
    retry_delay = 10
    while True:
        try:
            import threading
            threading.Thread(target=check_expired_memberships, daemon=True).start()
            logging.info("Starting bot polling...")
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            logging.error(f"Fatal error in polling: {str(e)}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)  # الحد الأقصى 5 دقائق
