# v3.5
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import string
import time
from datetime import datetime, timedelta
import os
import logging

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'
LOG_FILE = '/home/ec2-user/projects/WelMemBot/bot.log'

# إعداد التسجيل (Logging)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
                # جدول الأكواد
                c.execute('''CREATE TABLE IF NOT EXISTS codes
                            (code TEXT PRIMARY KEY, 
                             group_id TEXT, 
                             used INTEGER DEFAULT 0,
                             user_id INTEGER DEFAULT NULL,
                             expire_time TEXT DEFAULT NULL)''')
                # جدول العضويات
                c.execute('''CREATE TABLE IF NOT EXISTS memberships
                            (user_id INTEGER, 
                             group_id TEXT, 
                             join_date TEXT, 
                             PRIMARY KEY (user_id, group_id))''')
                # جدول المجموعات
                c.execute('''CREATE TABLE IF NOT EXISTS groups
                            (group_id TEXT PRIMARY KEY, 
                             welcome_message TEXT, 
                             is_private INTEGER DEFAULT 0)''')
                # جدول روابط الدعوة
                c.execute('''CREATE TABLE IF NOT EXISTS invite_links
                            (link TEXT PRIMARY KEY, 
                             group_id TEXT, 
                             user_id INTEGER,
                             code TEXT,
                             created_time TEXT, 
                             expire_time TEXT, 
                             used INTEGER DEFAULT 0)''')
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
            
            required_permissions = {
                'can_invite_users': bot_member.can_invite_users,
                'can_send_messages': bot_member.can_send_messages,
                'status': bot_member.status
            }
            
            logging.info(f"Bot permissions for chat {chat_id}: {required_permissions}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logging.warning(f"Bot is not an admin in chat {chat_id}")
                return False, "Bot needs to be admin with invite permissions"
                
            if not bot_member.can_invite_users:
                logging.warning(f"Bot can't invite users in chat {chat_id}")
                return False, "Bot needs invite users permission"
                
            return True, "Permissions OK"
            
        except telebot.apihelper.ApiTelegramException as e:
            error_msg = str(e).lower()
            if any(msg in error_msg for msg in ["chat not found", "bot is not a member", "blocked by user"]):
                logging.error(f"Bot access issue for chat {chat_id}: {error_msg}")
                return False, "Bot is not a member of this group"
            return False, f"Telegram API error: {str(e)}"
        except Exception as e:
            logging.error(f"Unexpected error checking permissions: {str(e)}")
            return False, f"Unexpected error: {str(e)}"

class CodeGenerator:
    """فئة لتوليد وإدارة الأكواد"""
    @staticmethod
    def generate_code(length=8):
        """توليد كود عشوائي"""
        characters = string.ascii_uppercase + string.digits  # أحرف كبيرة وأرقام فقط
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_multiple_codes(db_manager, group_id, count):
        """توليد عدة أكواد للمجموعة"""
        codes = []
        for _ in range(count):
            code = CodeGenerator.generate_code()
            db_manager.execute_query(
                "INSERT INTO codes (code, group_id) VALUES (?, ?)",
                (code, group_id)
            )
            codes.append(code)
        return codes

class InviteManager:
    """فئة لإدارة روابط الدعوة"""
    @staticmethod
    def create_invite_link(bot_instance, group_id, user_id, code):
        """إنشاء رابط دعوة مؤقت"""
        try:
            # إنشاء رابط صالح لمدة 24 ساعة لشخص واحد
            expire_date = int((datetime.now() + timedelta(hours=24)).timestamp()
            link = bot_instance.create_chat_invite_link(
                chat_id=group_id,
                name=f"Invite_{code}",
                expire_date=expire_date,
                member_limit=1
            )
            return link.invite_link, expire_date
        except Exception as e:
            logging.error(f"Error creating invite link: {str(e)}")
            return None, None
    
    @staticmethod
    def store_invite_link(db_manager, link_data):
        """تخزين رابط الدعوة في قاعدة البيانات"""
        try:
            db_manager.execute_query(
                """INSERT INTO invite_links 
                (link, group_id, user_id, code, created_time, expire_time) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                link_data
            )
            return True
        except Exception as e:
            logging.error(f"Error storing invite link: {str(e)}")
            return False

class MembershipManager:
    """فئة لإدارة العضويات"""
    @staticmethod
    def process_code(bot_instance, db_manager, user_id, code):
        """معالجة الكود وإرسال رابط الدعوة"""
        try:
            # التحقق من صحة الكود
            result = db_manager.execute_query(
                """SELECT group_id FROM codes 
                WHERE code = ? AND used = 0""",
                (code,),
                fetch=True
            )
            
            if not result:
                return False, "Invalid or used code"
            
            group_id = result[0][0]
            
            # التحقق من صلاحيات البوت
            success, msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not success:
                return False, msg
            
            # إنشاء رابط الدعوة
            invite_link, expire_time = InviteManager.create_invite_link(
                bot_instance, group_id, user_id, code)
            
            if not invite_link:
                return False, "Failed to create invite link"
            
            # تخزين معلومات الرابط
            link_data = (
                invite_link, group_id, user_id, code,
                datetime.now().isoformat(), expire_time
            )
            if not InviteManager.store_invite_link(db_manager, link_data):
                return False, "Failed to save invite link"
            
            # تحديث حالة الكود
            db_manager.execute_query(
                """UPDATE codes SET used = 1, 
                user_id = ?, expire_time = ? 
                WHERE code = ?""",
                (user_id, expire_time, code)
            )
            
            # إرسال رسالة الترحيب للمجموعة عند استخدام الرابط
            welcome_msg = MembershipManager.get_welcome_message(db_manager, group_id)
            username = bot_instance.get_chat(user_id).first_name
            bot.send_message(
                group_id,
                f"Welcome, {username}!\n"
                "Your membership will automatically expire after one month.\n"
                "Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."
            )
            
            return True, invite_link
            
        except Exception as e:
            logging.error(f"Error in process_code: {str(e)}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def get_welcome_message(db_manager, group_id):
        """الحصول على رسالة الترحيب للمجموعة"""
        result = db_manager.execute_query(
            "SELECT welcome_message FROM groups WHERE group_id = ?",
            (group_id,),
            fetch=True
        )
        return result[0][0] if result and result[0][0] else "Welcome to the group!"

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

def get_group_id(message):
    """الحصول على معرف المجموعة من الأدمن"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    group_id = message.text.strip()
    logging.info(f"Admin entered group_id: {group_id}")
    
    try:
        # التحقق من صلاحيات البوت
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        if not success:
            bot.reply_to(message, f"خطأ في الصلاحيات: {msg}")
            return
        
        # حفظ المجموعة في قاعدة البيانات
        chat = bot.get_chat(group_id)
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, "Welcome to the group!", int(chat.type in ['group', 'supergroup']))
        )
        
        bot.reply_to(message, f"تم تحديد المجموعة {chat.title} (ID: {group_id}). أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
        
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error in get_group_id: {str(e)}")

def generate_codes(message, group_id):
    """توليد الأكواد للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
            return
        
        codes = CodeGenerator.generate_multiple_codes(db_manager, group_id, num_codes)
        codes_str = "\n".join([f"🎟 الكود: {code}" for code in codes])
        bot.reply_to(message, f"تم توليد الأكواد التالية:\n{codes_str}\n\nيمكنك مشاركة هذه الأكواد مع الأعضاء للانضمام إلى المجموعة.")
        logging.info(f"Generated {num_codes} codes for group {group_id}")
        
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error generating codes: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip().upper()  # تحويل إلى أحرف كبيرة
    user_id = message.from_user.id
    username = message.from_user.first_name
    logging.info(f"User {user_id} entered code: {code}")
    
    success, result = MembershipManager.process_code(bot, db_manager, user_id, code)
    
    if success:
        bot.reply_to(message, f"مرحبًا {username}!\n\nرابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة):\n{result}\n\nسيتم إنهاء عضويتك بعد شهر تلقائيًا.")
    else:
        bot.reply_to(message, f"عذرًا {username}!\n{result}\nيرجى المحاولة لاحقًا أو التواصل مع المسؤول.")

@bot.message_handler(commands=['set_welcome'])
def set_welcome(message):
    """تعيين رسالة ترحيب مخصصة للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    try:
        if message.chat.type in ['group', 'supergroup']:
            group_id = str(message.chat.id)
            welcome_msg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        else:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                bot.reply_to(message, "يرجى إدخال معرف المجموعة ورسالة الترحيب! مثال: /set_welcome -1002329495586 Welcome!")
                return
            group_id, welcome_msg = parts[1], parts[2]
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message) VALUES (?, ?)",
            (group_id, welcome_msg)
        )
        bot.reply_to(message, f"تم تحديث رسالة الترحيب للمجموعة {group_id}!")
        logging.info(f"Updated welcome message for group {group_id}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nاستخدم:\n- داخل المجموعة: /set_welcome <رسالة الترحيب>\n- خارج المجموعة: /set_welcome <group_id> <رسالة الترحيب>")
        logging.error(f"Error in /set_welcome: {str(e)}")

# ===== الوظائف الخلفية =====

def check_expired_links_and_memberships():
    """فحص الروابط والعضويات المنتهية الصلاحية"""
    while True:
        try:
            # حذف روابط الدعوة المنتهية
            expired_links = db_manager.execute_query(
                "SELECT link FROM invite_links WHERE expire_time < ? AND used = 0",
                (datetime.now().timestamp(),),
                fetch=True
            )
            
            for (link,) in expired_links:
                db_manager.execute_query(
                    "UPDATE invite_links SET used = 1 WHERE link = ?",
                    (link,)
                )
            
            # حذف العضويات المنتهية (بعد 30 يومًا)
            expired_members = db_manager.execute_query(
                "SELECT user_id, group_id FROM memberships WHERE join_date < ?",
                ((datetime.now() - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for user_id, group_id in expired_members:
                try:
                    bot.kick_chat_member(group_id, user_id)
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (user_id, group_id)
                    )
                    logging.info(f"Removed expired member {user_id} from group {group_id}")
                except Exception as e:
                    logging.error(f"Error removing member {user_id}: {str(e)}")
            
            time.sleep(3600)  # التحقق كل ساعة
            
        except Exception as e:
            logging.error(f"Error in background check: {str(e)}")
            time.sleep(3600)

# بدء البوت
if __name__ == '__main__':
    try:
        # بدء الوظائف الخلفية في خيط منفصل
        import threading
        threading.Thread(target=check_expired_links_and_memberships, daemon=True).start()
        
        logging.info("Starting bot polling...")
        bot.polling(none_stop=True, interval=1, timeout=20)
    except Exception as e:
        logging.error(f"Fatal error in polling: {str(e)}")
        time.sleep(10)
