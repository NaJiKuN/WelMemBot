# x2.4
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import string
import time
from datetime import datetime, timedelta
import os
import logging
import threading
import sys
import retrying
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعدادات البوت
TOKEN = os.getenv('BOT_TOKEN') or '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = int(os.getenv('ADMIN_ID') or '764559466')
DB_PATH = os.getenv('DB_PATH') or '/home/ec2-user/projects/WelMemBot/codes.db'
LOG_FILE = os.getenv('LOG_FILE') or '/home/ec2-user/projects/WelMemBot/bot.log'

# المجموعة المعتمدة
APPROVED_GROUP_ID = os.getenv('APPROVED_GROUP_ID') or '-1002329495586'

# إعداد التسجيل (Logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
bot = telebot.TeleBot(TOKEN, num_threads=5)

class DatabaseManager:
    """فئة لإدارة عمليات قاعدة البيانات"""
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
        self._setup_default_group()
    
    def _init_db(self):
        """تهيئة قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS codes
                            (code TEXT PRIMARY KEY, 
                             group_id TEXT, 
                             used INTEGER DEFAULT 0,
                             user_id INTEGER DEFAULT NULL,
                             created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
                c.execute('''CREATE TABLE IF NOT EXISTS memberships
                            (user_id INTEGER, 
                             group_id TEXT, 
                             join_date TEXT, 
                             notified INTEGER DEFAULT 0,
                             PRIMARY KEY (user_id, group_id))''')
                c.execute('''CREATE TABLE IF NOT EXISTS groups
                            (group_id TEXT PRIMARY KEY, 
                             welcome_message TEXT, 
                             is_private INTEGER DEFAULT 0)''')
                conn.commit()
            logger.info("تم تهيئة قاعدة البيانات بنجاح")
        except sqlite3.Error as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {str(e)}")
            raise
    
    def _setup_default_group(self):
        """إعداد المجموعة المعتمدة مسبقًا"""
        try:
            self.execute_query(
                "INSERT OR IGNORE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
                (APPROVED_GROUP_ID, "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف.", 1)
            )
            logger.info("تم إعداد المجموعة المعتمدة مسبقًا بنجاح")
        except sqlite3.Error as e:
            logger.error(f"خطأ في إعداد المجموعة المعتمدة: {str(e)}")
    
    def execute_query(self, query, params=(), fetch=False):
        """تنفيذ استعلام على قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query, params)
                if fetch:
                    result = c.fetchall()
                    return result
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"خطأ في تنفيذ الاستعلام: {str(e)}")
            raise

class BotPermissions:
    """فئة للتحقق من صلاحيات البوت"""
    @staticmethod
    def check_bot_permissions(bot_instance, chat_id):
        """التحقق من صلاحيات البوت في المجموعة"""
        try:
            if str(chat_id) != APPROVED_GROUP_ID:
                logger.warning(f"المجموعة {chat_id} غير معتمدة")
                return False, "هذه المجموعة غير معتمدة"
            
            chat = bot_instance.get_chat(chat_id)
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            
            required_permissions = {
                'can_invite_users': bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else False,
                'can_send_messages': True,
                'can_restrict_members': bot_member.can_restrict_members if hasattr(bot_member, 'can_restrict_members') else False,
                'status': bot_member.status
            }
            
            logger.info(f"صلاحيات البوت في المجموعة {chat_id}: {required_permissions}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logger.warning(f"البوت ليس مشرفًا في المجموعة {chat_id}")
                return False, "البوت يجب أن يكون مشرفاً في المجموعة"
                
            if not required_permissions['can_invite_users']:
                logger.warning("البوت لا يملك صلاحية إضافة أعضاء")
                return False, "البوت يحتاج صلاحية إضافة أعضاء"
                
            if not required_permissions['can_restrict_members']:
                logger.warning("البوت لا يملك صلاحية تقييد الأعضاء")
                return False, "البوت يحتاج صلاحية تقييد الأعضاء"
                
            return True, "الصلاحيات كافية"
            
        except telebot.apihelper.ApiTelegramException as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg:
                return False, "المجموعة غير موجودة"
            elif "bot is not a member" in error_msg:
                return False, "البوت ليس عضواً في المجموعة"
            logger.error(f"خطأ في API تيليجرام أثناء التحقق من الصلاحيات: {str(e)}")
            return False, f"خطأ في API تيليجرام: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع في التحقق من الصلاحيات: {str(e)}")
            return False, f"خطأ غير متوقع: {str(e)}"

class CodeGenerator:
    """فئة لتوليد وإدارة الأكواد"""
    @staticmethod
    def generate_code(length=8):
        """توليد كود عشوائي"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_multiple_codes(db_manager, group_id, count):
        """توليد عدة أكواد للمجموعة"""
        if str(group_id) != APPROVED_GROUP_ID:
            logger.error(f"محاولة توليد أكواد لمجموعة غير معتمدة: {group_id}")
            return []
        
        codes = []
        attempts = 0
        max_attempts = count * 2
        while len(codes) < count and attempts < max_attempts:
            code = CodeGenerator.generate_code()
            try:
                db_manager.execute_query(
                    "INSERT INTO codes (code, group_id) VALUES (?, ?)",
                    (code, group_id)
                )
                codes.append(code)
            except sqlite3.IntegrityError:
                attempts += 1
                continue
        if attempts >= max_attempts:
            logger.warning(f"تجاوز عدد المحاولات لتوليد الأكواد للمجموعة {group_id}")
        return codes

class MembershipManager:
    """فئة لإدارة العضويات"""
    @staticmethod
    def process_code(bot_instance, db_manager, user_id, code):
        """معالجة الكود وإرسال رابط الدعوة"""
        try:
            logger.info(f"معالجة الكود {code} للمستخدم {user_id}")
            result = db_manager.execute_query(
                """SELECT group_id FROM codes 
                WHERE code = ? AND used = 0""",
                (code,),
                fetch=True
            )
            
            if not result:
                logger.warning(f"الكود {code} غير صالح أو مستخدم من قبل")
                return False, "الكود غير صالح أو مستخدم من قبل"
            
            group_id = result[0]['group_id']
            if str(group_id) != APPROVED_GROUP_ID:
                logger.error(f"محاولة معالجة كود لمجموعة غير معتمدة: {group_id}")
                return False, "المجموعة غير معتمدة. تواصل مع المسؤول."
            
            logger.info(f"الكود {code} مرتبط بالمجموعة {group_id}")
            
            success, message = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not success:
                return False, message
                
            try:
                invite_link = bot_instance.create_chat_invite_link(
                    chat_id=group_id,
                    name=f"Invite_{code}",
                    member_limit=1,
                    expire_date=int(time.time()) + 86400
                )
                
                db_manager.execute_query(
                    """UPDATE codes SET user_id = ?, used = 1 
                    WHERE code = ?""",
                    (user_id, code)
                )
                
                return True, invite_link.invite_link
                
            except telebot.apihelper.ApiTelegramException as e:
                error_msg = str(e).lower()
                if "user is already a participant" in error_msg:
                    logger.info(f"المستخدم {user_id} بالفعل عضو في المجموعة {group_id}")
                    return False, "أنت بالفعل عضو في المجموعة!"
                elif "not enough rights" in error_msg:
                    return False, "البوت لا يملك الصلاحيات الكافية في المجموعة"
                else:
                    logger.error(f"خطأ في إنشاء رابط الدعوة: {str(e)}")
                    return False, f"حدث خطأ: {str(e)}"
            
        except sqlite3.Error as e:
            logger.error(f"خطأ في معالجة الكود: {str(e)}")
            return False, f"خطأ في قاعدة البيانات: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع في معالجة الكود: {str(e)}")
            return False, f"حدث خطأ: {str(e)}"
    
    @staticmethod
    def send_welcome_message(bot_instance, db_manager, chat_id, user_id):
        """إرسال رسالة ترحيبية عند الانضمام"""
        try:
            if str(chat_id) != APPROVED_GROUP_ID:
                logger.warning(f"محاولة إرسال رسالة ترحيب لمجموعة غير معتمدة: {chat_id}")
                return False
            
            user = bot_instance.get_chat(user_id)
            username = user.first_name or user.username or f"User_{user_id}"
            
            welcome_result = db_manager.execute_query(
                "SELECT welcome_message FROM groups WHERE group_id = ?",
                (str(chat_id),),
                fetch=True
            )
            welcome_msg_template = welcome_result[0]['welcome_message'] if welcome_result else \
                "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف."
            
            welcome_msg = welcome_msg_template.format(username=username)
            
            existing = db_manager.execute_query(
                "SELECT 1 FROM memberships WHERE user_id = ? AND group_id = ?",
                (user_id, str(chat_id)),
                fetch=True
            )
            if not existing:
                db_manager.execute_query(
                    """INSERT INTO memberships 
                    (user_id, group_id, join_date) 
                    VALUES (?, ?, ?)""",
                    (user_id, str(chat_id), datetime.now().isoformat())
                )
            
            try:
                bot_instance.send_message(chat_id, welcome_msg)
                logger.info(f"تم إرسال رسالة الترحيب إلى المجموعة {chat_id} للمستخدم {user_id}")
            except telebot.apihelper.ApiTelegramException as e:
                if "can't send messages" in str(e).lower():
                    bot_instance.send_message(ADMIN_ID, f"لا يمكنني إرسال رسائل في المجموعة {chat_id}. رسالة الترحيب لـ {username}:\n{welcome_msg}")
                    logger.warning(f"لا يمكن إرسال رسائل في المجموعة {chat_id}. تم إرسال رسالة الترحيب إلى الأدمن.")
                else:
                    raise e
            return True
        except (sqlite3.Error, telebot.apihelper.ApiTelegramException) as e:
            logger.error(f"خطأ في إرسال رسالة الترحيب: {str(e)}")
            return False
    
    @staticmethod
    @retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
    def notify_expired_memberships(bot_instance, db_manager):
        """إرسال إشعارات للأعضاء المنتهية عضويتهم"""
        try:
            expired_members = db_manager.execute_query(
                """SELECT user_id, group_id, join_date 
                FROM memberships 
                WHERE join_date < ? AND notified = 0""",
                ((datetime.now() - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for member in expired_members:
                try:
                    if str(member['group_id']) != APPROVED_GROUP_ID:
                        continue
                    user = bot_instance.get_chat(member['user_id'])
                    username = user.first_name or user.username or f"User_{member['user_id']}"
                    bot_instance.send_message(
                        ADMIN_ID,
                        f"تم إنهاء عضوية العضو: {username} (ID: {member['user_id']})\n"
                        f"المجموعة: {member['group_id']}\n"
                        f"تاريخ الانضمام: {member['join_date']}"
                    )
                    
                    db_manager.execute_query(
                        """UPDATE memberships 
                        SET notified = 1 
                        WHERE user_id = ? AND group_id = ?""",
                        (member['user_id'], member['group_id'])
                    )
                    logger.info(f"تم إرسال إشعار للأدمن عن انتهاء عضوية {member['user_id']}")
                    
                except telebot.apihelper.ApiTelegramException as e:
                    logger.error(f"خطأ في إرسال إشعار للمسؤول: {str(e)}")
            
            return True
        except sqlite3.Error as e:
            logger.error(f"خطأ في إشعارات العضويات المنتهية: {str(e)}")
            return False

# تهيئة مدير قاعدة البيانات
db_manager = DatabaseManager(DB_PATH)

# ===== معالجات الأوامر =====

@bot.message_handler(commands=['start', 'help'])
def start(message):
    """معالجة أمر /start"""
    user_id = message.from_user.id
    logger.info(f"أمر /start من المستخدم {user_id}")
    
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("إنشاء أكواد جديدة", callback_data="generate_codes"))
        markup.add(InlineKeyboardButton("عرض الأكواد", callback_data="show_codes"))
        
        bot.reply_to(message, "مرحبًا أيها الأدمن! اختر الإجراء المطلوب:", reply_markup=markup)
    else:
        bot.reply_to(message, "أدخل الكود الخاص بك للانضمام إلى المجموعة:")
        bot.register_next_step_handler(message, check_code)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة الأزرار"""
    try:
        if call.data == "generate_codes":
            bot.send_message(call.message.chat.id, f"سيتم إنشاء الأكواد للمجموعة {APPROVED_GROUP_ID}. أدخل عدد الأكواد المطلوبة:")
            bot.register_next_step_handler(call.message, lambda m: generate_codes(m, APPROVED_GROUP_ID))
        elif call.data == "show_codes":
            show_codes(call.message)
            
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار: {str(e)}")
        bot.answer_callback_query(call.id, "حدث خطأ، يرجى المحاولة لاحقًا")

def generate_codes(message, group_id):
    """توليد الأكواد للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0 or num_codes > 100:  # تحديد الحد الأقصى
            bot.reply_to(message, "يرجى إدخال عدد صحيح بين 1 و100.")
            return
        
        success, message_text = BotPermissions.check_bot_permissions(bot, group_id)
        if not success:
            bot.reply_to(message, message_text)
            return
            
        codes = CodeGenerator.generate_multiple_codes(db_manager, group_id, num_codes)
        if not codes:
            bot.reply_to(message, "حدث خطأ أثناء توليد الأكواد. يرجى المحاولة مرة أخرى.")
            return
            
        codes_str = "\n".join([f"`{code}`" for code in codes])
        bot.reply_to(message, 
                    f"تم توليد الأكواد التالية للمجموعة {group_id}:\n{codes_str}\n\n"
                    "يمكنك نسخ الأكواد من الأعلى أو مشاركتها مع الأعضاء للانضمام إلى المجموعة.",
                    parse_mode='Markdown')
        
        logger.info(f"تم توليد {len(codes)} أكواد للمجموعة {group_id}")
        
    except ValueError:
        bot.reply_to(message, "يرجى إدخال رقم صحيح!")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logger.error(f"خطأ في توليد الأكواد: {str(e)}")

def show_codes(message):
    """عرض الأكواد"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
        
    try:
        used_codes = db_manager.execute_query(
            """SELECT code, user_id, created_at 
            FROM codes 
            WHERE group_id = ? AND used = 1
            ORDER BY created_at DESC""",
            (APPROVED_GROUP_ID,),
            fetch=True
        )
        
        unused_codes = db_manager.execute_query(
            """SELECT code, created_at 
            FROM codes 
            WHERE group_id = ? AND used = 0
            ORDER BY created_at DESC""",
            (APPROVED_GROUP_ID,),
            fetch=True
        )
        
        msg = f"معلومات المجموعة {APPROVED_GROUP_ID}:\n\n"
        
        msg += "📌 الأكواد غير المستخدمة:\n"
        if unused_codes:
            msg += "\n".join([f"- `{code['code']}` (أنشئ في: {code['created_at']})" for code in unused_codes])
        else:
            msg += "لا توجد أكواد غير مستخدمة"
        msg += "\n\n"
        
        msg += "🔑 الأكواد المستخدمة:\n"
        if used_codes:
            msg += "\n".join([f"- `{code['code']}` بواسطة {code['user_id']} (أنشئ في: {code['created_at']})" for code in used_codes])
        else:
            msg += "لا توجد أكواد مستخدمة"
        
        bot.reply_to(message, msg, parse_mode='Markdown')
    except sqlite3.Error as e:
        bot.reply_to(message, f"خطأ في قاعدة البيانات: {str(e)}")
        logger.error(f"خطأ في عرض الأكواد: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip().upper()
    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username or "عضو جديد"
    logger.info(f"الكود المدخل من المستخدم {user_id}: {code}")
    
    if not code or len(code) != 8 or not code.isalnum():
        bot.reply_to(message, f"عذرًا {username}!\nالكود غير صالح. يجب أن يكون 8 أحرف أو أرقام. يرجى المحاولة مرة أخرى.")
        return
        
    success, result = MembershipManager.process_code(bot, db_manager, user_id, code)
    
    if success:
        bot.reply_to(message, 
                    f"مرحبًا {username}!\n\n"
                    f"رابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة):\n{result}\n\n"
                    "انقر على الرابط للانضمام إلى المجموعة.")
        logger.info(f"تم إرسال رابط الدعوة للمستخدم {user_id}")
    else:
        bot.reply_to(message, f"عذرًا {username}!\n{result}\nيرجى المحاولة لاحقًا أو التواصل مع المسؤول.")
        logger.warning(f"فشل في معالجة الكود {code} للمستخدم {user_id}: {result}")

@bot.message_handler(commands=['set_welcome'])
def set_welcome(message):
    """تعيين رسالة ترحيب مخصصة للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    try:
        welcome_msg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        
        if not welcome_msg:
            bot.reply_to(message, 
                        "يرجى إدخال رسالة الترحيب!\n"
                        "مثال: /set_welcome 🎉 مرحبًا بك، {username}!\n"
                        "📅 عضويتك ستنتهي بعد شهر.\n📜 يرجى الالتزام بقواعد المجموعة.\n"
                        "يمكن استخدام {username} لاستبدال اسم العضو تلقائيًا.")
            return
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message) VALUES (?, ?)",
            (APPROVED_GROUP_ID, welcome_msg)
        )
        bot.reply_to(message, f"تم تحديث رسالة الترحيب للمجموعة {APPROVED_GROUP_ID} بنجاح!")
        logger.info(f"تم تحديث رسالة الترحيب للمجموعة {APPROVED_GROUP_ID} إلى: {welcome_msg}")
    except sqlite3.Error as e:
        bot.reply_to(message, f"خطأ في قاعدة البيانات: {str(e)}")
        logger.error(f"خطأ في تعيين رسالة الترحيب: {str(e)}")

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    """معالجة الأعضاء الجدد عند اضافتهم إلى المجموعة"""
    try:
        chat_id = message.chat.id
        if str(chat_id) != APPROVED_GROUP_ID:
            return
            
        success, message_text = BotPermissions.check_bot_permissions(bot, chat_id)
        if not success:
            bot.send_message(ADMIN_ID, f"خطأ في الصلاحيات بالمجموعة {chat_id}: {message_text}")
            return
            
        for new_member in message.new_chat_members:
            user_id = new_member.id
            logger.info(f"عضو جديد تمت إضافته إلى المجموعة: {user_id}")
            
            MembershipManager.send_welcome_message(bot, db_manager, chat_id, user_id)
            
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"خطأ في معالجة العضو الجديد: {str(e)}")

@retrying.retry(stop_max_attempt_number=5, wait_fixed=3600000)  # إعادة المحاولة كل ساعة
def check_expired_memberships():
    """فحص العضويات المنتهية الصلاحية"""
    try:
        now = datetime.now()
        
        expired_members = db_manager.execute_query(
            "SELECT user_id, group_id FROM memberships WHERE join_date < ?",
            ((now - timedelta(days=30)).isoformat(),),
            fetch=True
        )
        
        for member in expired_members:
            if str(member['group_id']) != APPROVED_GROUP_ID:
                continue
            try:
                bot.kick_chat_member(member['group_id'], member['user_id'])
                db_manager.execute_query(
                    "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                    (member['user_id'], member['group_id'])
                )
                logger.info(f"تم إزالة العضو المنتهية عضويته {member['user_id']} من المجموعة {member['group_id']}")
            except telebot.apihelper.ApiTelegramException as e:
                if "user not found" in str(e).lower():
                    logger.warning(f"العضو {member['user_id']} غير موجود في المجموعة {member['group_id']}")
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (member['user_id'], member['group_id'])
                    )
                else:
                    logger.error(f"خطأ في طرد العضو {member['user_id']}: {str(e)}")
        
        MembershipManager.notify_expired_memberships(bot, db_manager)
        
    except (sqlite3.Error, telebot.apihelper.ApiTelegramException) as e:
        logger.error(f"خطأ في الفحص الخلفي: {str(e)}")
        raise

# بدء البوت
if __name__ == '__main__':
    try:
        # التحقق من صلاحيات البوت عند البدء
        success, message = BotPermissions.check_bot_permissions(bot, APPROVED_GROUP_ID)
        if not success:
            logger.error(f"فشل التحقق من الصلاحيات: {message}")
            bot.send_message(ADMIN_ID, f"فشل التحقق من الصلاحيات: {message}")
            sys.exit(1)
            
        # بدء الفحص الخلفي في خيط منفصل
        bg_thread = threading.Thread(target=check_expired_memberships, daemon=True)
        bg_thread.start()
        
        logger.info("جاري تشغيل البوت...")
        bot.infinity_polling()
        
    except KeyboardInterrupt:
        logger.info("إيقاف البوت...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
        bot.send_message(ADMIN_ID, f"خطأ غير متوقع: {str(e)}")
        sys.exit(1)
