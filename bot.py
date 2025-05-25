# v3.4
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
                c.execute('''CREATE TABLE IF NOT EXISTS codes
                            (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER DEFAULT 0)''')
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
            
            # إذا كانت المجموعة خاصة، لا نحتاج لتحقق مشددة من الصلاحيات
            if chat.type in ['group', 'supergroup']:
                try:
                    bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
                    return bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else True
                except:
                    return True
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking permissions: {str(e)}")
            return False

class CodeGenerator:
    """فئة لتوليد وإدارة الأكواد"""
    @staticmethod
    def generate_code(length=8):
        """توليد كود عشوائي"""
        characters = string.ascii_letters + string.digits
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

class MembershipManager:
    """فئة لإدارة العضويات"""
    @staticmethod
    def add_member(bot_instance, db_manager, user_id, group_id, code):
        """إضافة عضو جديد إلى المجموعة"""
        try:
            # التحقق من صلاحيات البوت
            if not BotPermissions.check_bot_permissions(bot_instance, group_id):
                return False, "البوت ليس لديه الصلاحيات الكافية في المجموعة"
            
            # محاولة إضافة العضو بعدة طرق
            try:
                # 1. محاولة الحصول على رابط الدعوة
                chat = bot_instance.get_chat(group_id)
                if chat.invite_link:
                    bot_instance.send_message(user_id, f"انضم للمجموعة من خلال الرابط: {chat.invite_link}")
                    success = True
                else:
                    # 2. محاولة رفع الحظر إذا كان موجودًا
                    try:
                        bot_instance.unban_chat_member(group_id, user_id)
                        success = True
                    except:
                        success = False
                    
                    # 3. إرسال طلب إضافة يدوية للمشرفين
                    try:
                        user_info = bot_instance.get_chat(user_id)
                        username = f"@{user_info.username}" if user_info.username else f"المستخدم (ID: {user_id})"
                        bot_instance.send_message(
                            group_id,
                            f"الرجاء إضافة {username} إلى المجموعة. كود الانضمام: {code}"
                        )
                        success = True
                    except:
                        success = False
                
                if not success:
                    return False, "لا يمكن إضافتك تلقائيًا. يرجى التواصل مع المسؤول."
                
            except Exception as e:
                logging.error(f"Error adding member: {str(e)}")
                return False, "حدث خطأ أثناء محاولة إضافتك للمجموعة"
            
            # تحديث قاعدة البيانات
            db_manager.execute_query(
                "UPDATE codes SET used = 1 WHERE code = ?", 
                (code,)
            )
            db_manager.execute_query(
                "INSERT INTO memberships (user_id, group_id, join_date) VALUES (?, ?, ?)",
                (user_id, group_id, datetime.now().isoformat())
            )
            
            # إرسال رسالة الترحيب
            welcome_msg = MembershipManager.get_welcome_message(db_manager, group_id)
            try:
                bot_instance.send_message(group_id, welcome_msg)
            except:
                logging.warning(f"Couldn't send welcome message to group {group_id}")
            
            return True, "تمت إضافتك إلى المجموعة بنجاح!"
            
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
        
        if result and result[0][0]:
            return result[0][0]
        else:
            return f"مرحبًا بك في المجموعة! يرجى الالتزام بالقواعد."

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
        bot.reply_to(message, f"معرف هذه المجموعة هو: {message.chat.id}\n"
                             f"يمكنك استخدامه لإعداد البوت.")
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
        # محاولة الحصول على معلومات المجموعة للتحقق من وجودها
        chat = bot.get_chat(group_id)
        
        # تحديد نوع المجموعة
        is_private = chat.type in ['group', 'supergroup']
        
        if not BotPermissions.check_bot_permissions(bot, group_id):
            bot.reply_to(message, "البوت ليس لديه الصلاحيات الكافية في المجموعة! تأكد من:")
            bot.reply_to(message, "1. أن البوت عضو في المجموعة\n"
                                "2. أن لديه صلاحية إضافة أعضاء\n"
                                "3. إذا كانت المجموعة خاصة، قد تحتاج إلى إرسال دعوة للبوت")
            return
        
        # حفظ المجموعة في قاعدة البيانات
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, "مرحبًا بك في مجموعتنا! يرجى قراءة القواعد.", int(is_private))
        )
        
        bot.reply_to(message, f"تم تحديد المجموعة {chat.title} (ID: {group_id}). أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
        
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nتأكد من:\n"
                             f"1. أن البوت عضو في المجموعة\n"
                             f"2. أنك أدخلت المعرف بشكل صحيح\n"
                             f"3. يمكنك الحصول على معرف المجموعة بإرسال /id داخل المجموعة")
    except Exception as e:
        bot.reply_to(message, f"خطأ غير متوقع: {str(e)}")
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
        bot.reply_to(message, f"تم توليد الأكواد التالية:\n{codes_str}\n\n"
                             f"يمكنك مشاركة هذه الأكواد مع الأعضاء للانضمام إلى المجموعة.")
        logging.info(f"Generated {num_codes} codes for group {group_id}")
        
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logging.error(f"Error generating codes: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.first_name
    logging.info(f"User {user_id} entered code: {code}")
    
    result = db_manager.execute_query(
        "SELECT group_id FROM codes WHERE code = ? AND used = 0",
        (code,),
        fetch=True
    )
    
    if not result:
        bot.reply_to(message, "الكود غير صالح أو مستخدم من قبل! يرجى التأكد من الكود والمحاولة مرة أخرى.")
        return
    
    group_id = result[0][0]
    success, msg = MembershipManager.add_member(bot, db_manager, user_id, group_id, code)
    
    if success:
        bot.reply_to(message, f"مرحبًا {username}!\n{msg}")
    else:
        bot.reply_to(message, f"عذرًا {username}!\n{msg}\nيرجى التواصل مع المسؤول للمساعدة.")

@bot.message_handler(commands=['set_welcome'])
def set_welcome(message):
    """تعيين رسالة ترحيب مخصصة للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    try:
        # إذا تم إرسال الأمر داخل المجموعة
        if message.chat.type in ['group', 'supergroup']:
            group_id = str(message.chat.id)
            welcome_msg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        else:
            # إذا تم إرسال الأمر في محادثة خاصة مع معرف المجموعة
            _, group_id, *welcome_parts = message.text.split(maxsplit=2)
            welcome_msg = welcome_parts[0] if welcome_parts else ""
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message) VALUES (?, ?)",
            (group_id, welcome_msg)
        )
        
        bot.reply_to(message, f"تم تحديث رسالة الترحيب للمجموعة {group_id}!")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nاستخدم:\n"
                             f"- داخل المجموعة: /set_welcome <رسالة الترحيب>\n"
                             f"- خارج المجموعة: /set_welcome <group_id> <رسالة الترحيب>")

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
                    # محاولة طرد العضو المنتهية صلاحيته
                    bot.kick_chat_member(group_id, user_id)
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (user_id, group_id)
                    )
                    logging.info(f"User {user_id} removed from group {group_id}")
                except Exception as e:
                    logging.error(f"Error removing user {user_id}: {str(e)}")
            
            time.sleep(86400)  # التحقق كل 24 ساعة
            
        except Exception as e:
            logging.error(f"Error in membership check: {str(e)}")
            time.sleep(3600)  # إعادة المحاولة بعد ساعة في حالة الخطأ

# بدء البوت
if __name__ == '__main__':
    try:
        # بدء فحص العضويات المنتهية في خيط منفصل
        import threading
        threading.Thread(target=check_expired_memberships, daemon=True).start()
        
        logging.info("Starting bot polling...")
        bot.polling(none_stop=True, interval=1, timeout=20)
        
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        time.sleep(10)
