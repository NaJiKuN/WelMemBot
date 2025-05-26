# x2.2
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

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'
LOG_FILE = '/home/ec2-user/projects/WelMemBot/bot.log'

# قائمة المجموعات المعتمدة
APPROVED_GROUP_IDS = ['-1002329495586']

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
        self._setup_default_groups()
    
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
                             created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
                # جدول العضويات
                c.execute('''CREATE TABLE IF NOT EXISTS memberships
                            (user_id INTEGER, 
                             group_id TEXT, 
                             join_date TEXT, 
                             notified INTEGER DEFAULT 0,
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
                             expire_time INTEGER,
                             used INTEGER DEFAULT 0)''')
                conn.commit()
            logger.info("تم تهيئة قاعدة البيانات بنجاح")
        except Exception as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {str(e)}")
            raise
    
    def _setup_default_groups(self):
        """إعداد المجموعات المعتمدة مسبقًا"""
        try:
            for group_id in APPROVED_GROUP_IDS:
                self.execute_query(
                    "INSERT OR IGNORE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
                    (group_id, "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف.", 1)
                )
            logger.info("تم إعداد المجموعات المعتمدة مسبقًا بنجاح")
        except Exception as e:
            logger.error(f"خطأ في إعداد المجموعات المعتمدة: {str(e)}")
    
    def execute_query(self, query, params=(), fetch=False):
        """تنفيذ استعلام على قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query, params)
                if fetch:
                    result = c.fetchall()
                    return result
                conn.commit()
        except Exception as e:
            logger.error(f"خطأ في تنفيذ الاستعلام: {str(e)}")
            raise

class BotPermissions:
    """فئة للتحقق من صلاحيات البوت"""
    @staticmethod
    def check_bot_permissions(bot_instance, chat_id):
        """التحقق من صلاحيات البوت في المجموعة"""
        try:
            if str(chat_id) not in APPROVED_GROUP_IDS:
                logger.warning(f"المجموعة {chat_id} غير معتمدة")
                return False, "هذه المجموعة غير معتمدة. تواصل مع المسؤول للاعتماد."
            
            chat = bot_instance.get_chat(chat_id)
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            
            required_permissions = {
                'can_invite_users': bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else False,
                'can_restrict_members': bot_member.can_restrict_members if hasattr(bot_member, 'can_restrict_members') else False,
                'status': bot_member.status
            }
            
            logger.info(f"صلاحيات البوت في المجموعة {chat_id}: {required_permissions}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logger.warning(f"البوت ليس مشرفًا في المجموعة {chat_id}")
                return False, "البوت يجب أن يكون مشرفاً في المجموعة"
                
            missing_permissions = []
            if not required_permissions['can_invite_users']:
                missing_permissions.append("إضافة أعضاء")
            if not required_permissions['can_restrict_members']:
                missing_permissions.append("حظر أعضاء")
                
            if missing_permissions:
                error_msg = f"البوت يحتاج الصلاحيات التالية: {', '.join(missing_permissions)}"
                logger.warning(error_msg)
                return False, error_msg
                
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
        if str(group_id) not in APPROVED_GROUP_IDS:
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

class InviteManager:
    """فئة لإدارة روابط الدعوة"""
    @staticmethod
    def create_invite_link(bot_instance, group_id, user_id, code):
        """إنشاء رابط دعوة مؤقت"""
        if str(group_id) not in APPROVED_GROUP_IDS:
            logger.error(f"محاولة إنشاء رابط دعوة لمجموعة غير معتمدة: {group_id}")
            return None, None, "المجموعة غير معتمدة"
        
        try:
            logger.info(f"محاولة إنشاء رابط دعوة للمجموعة {group_id} بواسطة المستخدم {user_id} باستخدام الكود {code}")
            expire_date = int(time.time()) + 86400  # 24 ساعة
            link = bot_instance.create_chat_invite_link(
                chat_id=group_id,
                name=f"Invite_{code}",
                expire_date=expire_date,
                member_limit=1
            )
            logger.info(f"تم إنشاء رابط الدعوة بنجاح: {link.invite_link}")
            return link.invite_link, expire_date, None
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"خطأ في API تيليجرام أثناء إنشاء رابط الدعوة: {str(e)}")
            error_msg = str(e).lower()
            if "need administrator rights" in error_msg or "chat invite link" in error_msg:
                return None, None, "البوت يحتاج صلاحية إضافة أعضاء (can_invite_users) لإنشاء رابط دعوة"
            elif "privacy settings" in error_msg:
                return None, None, "يرجى تعطيل إعدادات الخصوصية في @BotFather باستخدام /setprivacy -> Disabled"
            elif "chat not found" in error_msg:
                return None, None, "المجموعة غير موجودة أو المعرف غير صحيح"
            elif "bot is not a member" in error_msg:
                return None, None, "البوت ليس عضواً في المجموعة"
            return None, None, f"خطأ في API تيليجرام: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع أثناء إنشاء رابط الدعوة: {str(e)}")
            return None, None, f"خطأ غير متوقع: {str(e)}"
    
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
            logger.info(f"تم تخزين رابط الدعوة بنجاح: {link_data[0]}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تخزين رابط الدعوة: {str(e)}")
            return False
    
    @staticmethod
    def get_invite_links(db_manager, group_id=None):
        """الحصول على روابط الدعوة"""
        try:
            if group_id:
                result = db_manager.execute_query(
                    """SELECT * FROM invite_links 
                    WHERE group_id = ? 
                    ORDER BY created_time DESC""",
                    (group_id,),
                    fetch=True
                )
            else:
                result = db_manager.execute_query(
                    """SELECT * FROM invite_links 
                    ORDER BY created_time DESC""",
                    fetch=True
                )
            return result
        except Exception as e:
            logger.error(f"خطأ في جلب روابط الدعوة: {str(e)}")
            return None

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
            if str(group_id) not in APPROVED_GROUP_IDS:
                logger.error(f"محاولة معالجة كود لمجموعة غير معتمدة: {group_id}")
                return False, "المجموعة غير معتمدة. تواصل مع المسؤول."
            
            logger.info(f"الكود {code} مرتبط بالمجموعة {group_id}")
            
            try:
                member = bot_instance.get_chat_member(group_id, user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    logger.info(f"المستخدم {user_id} بالفعل عضو في المجموعة {group_id}")
                    return False, "أنت بالفعل عضو في المجموعة!"
            except telebot.apihelper.ApiTelegramException as e:
                if "user not found" not in str(e).lower():
                    logger.error(f"خطأ في التحقق من حالة العضوية: {str(e)}")
                    return False, f"خطأ في التحقق من حالة العضوية: {str(e)}"
            
            success, msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not success:
                logger.warning(f"فشل في التحقق من الصلاحيات للمجموعة {group_id}: {msg}")
                return False, msg
            
            invite_link, expire_time, error_msg = InviteManager.create_invite_link(
                bot_instance, group_id, user_id, code)
            
            if not invite_link:
                logger.error(f"فشل في إنشاء رابط الدعوة: {error_msg}")
                return False, error_msg or "فشل في إنشاء رابط الدعوة"
            
            link_data = (
                invite_link, group_id, user_id, code,
                datetime.now().isoformat(), expire_time
            )
            if not InviteManager.store_invite_link(db_manager, link_data):
                logger.error("فشل في حفظ رابط الدعوة")
                return False, "فشل في حفظ رابط الدعوة"
            
            db_manager.execute_query(
                """UPDATE codes SET user_id = ?, used = 1 
                WHERE code = ?""",
                (user_id, code)
            )
            logger.info(f"تم تحديث الكود {code} كمستخدم من قبل {user_id}")
            
            return True, invite_link
            
        except Exception as e:
            logger.error(f"خطأ في معالجة الكود: {str(e)}")
            return False, f"حدث خطأ: {str(e)}"
    
    @staticmethod
    def send_welcome_message(bot_instance, db_manager, chat_id, user_id):
        """إرسال رسالة ترحيبية عند الانضمام"""
        try:
            if str(chat_id) not in APPROVED_GROUP_IDS:
                logger.warning(f"محاولة إرسال رسالة ترحيب لمجموعة غير معتمدة: {chat_id}")
                return False
            
            user = bot_instance.get_chat(user_id)
            username = user.first_name or user.username or f"User_{user_id}"
            # جلب الرسالة الترحيبية من قاعدة البيانات
            welcome_result = db_manager.execute_query(
                "SELECT welcome_message FROM groups WHERE group_id = ?",
                (str(chat_id),),
                fetch=True
            )
            welcome_msg_template = welcome_result[0]['welcome_message'] if welcome_result else \
                "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف."
            
            # استبدال {username} باسم المستخدم
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
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة الترحيب: {str(e)}")
            return False
    
    @staticmethod
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
                    if str(member['group_id']) not in APPROVED_GROUP_IDS:
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
                    
                except Exception as e:
                    logger.error(f"خطأ في إرسال إشعار للمسؤول: {str(e)}")
            
            return True
        except Exception as e:
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
        markup.add(InlineKeyboardButton("عرض الأكواد والروابط", callback_data="show_codes_links"))
        
        bot.reply_to(message, "مرحبًا أيها الأدمن! اختر الإجراء المطلوب:", reply_markup=markup)
    else:
        bot.reply_to(message, "أدخل الكود الخاص بك للانضمام إلى المجموعة:")
        bot.register_next_step_handler(message, check_code)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة الأزرار"""
    try:
        if call.data == "generate_codes":
            bot.send_message(call.message.chat.id, "أدخل معرف المجموعة:")
            bot.register_next_step_handler(call.message, get_group_id)
        elif call.data == "show_codes_links":
            show_codes_links(call.message)
        elif call.data.startswith("group_"):
            group_id = call.data.split("_")[1]
            show_group_links(call.message, group_id)
            
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار: {str(e)}")
        bot.answer_callback_query(call.id, "حدث خطأ، يرجى المحاولة لاحقًا")

def get_group_id(message):
    """الحصول على معرف المجموعة من الأدمن"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    group_id = message.text.strip()
    logger.info(f"معرف المجموعة المدخل: {group_id}")
    
    try:
        if not group_id.startswith('-100'):
            bot.reply_to(message, "معرف المجموعة غير صالح! يجب أن يبدأ بـ -100.")
            return
            
        if str(group_id) not in APPROVED_GROUP_IDS:
            bot.reply_to(message, f"معرف المجموعة {group_id} غير معتمد. تواصل مع المطور لإضافته إلى القائمة المعتمدة.")
            return
            
        chat = bot.get_chat(group_id)
        
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        if not success:
            bot.reply_to(message, f"خطأ في الصلاحيات: {msg}")
            return
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف.", int(chat.type in ['group', 'supergroup']))
        )
        
        bot.reply_to(message, f"تم تحديد المجموعة {chat.title} (ID: {group_id}). أدخل عدد الأكواد المطلوبة:")
        bot.register_next_step_handler(message, lambda m: generate_codes(m, group_id))
        
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")
        logger.error(f"خطأ في الحصول على معرف المجموعة: {str(e)}")

def generate_codes(message, group_id):
    """توليد الأكواد للمجموعة"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    if str(group_id) not in APPROVED_GROUP_IDS:
        bot.reply_to(message, f"المجموعة {group_id} غير معتمدة. تواصل مع المطور لإضافتها.")
        return
    
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
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

def show_codes_links(message):
    """عرض الأكواد والروابط"""
    try:
        groups = db_manager.execute_query(
            "SELECT group_id FROM groups",
            fetch=True
        )
        
        if not groups:
            bot.reply_to(message, "لا توجد مجموعات مسجلة.")
            return
            
        markup = InlineKeyboardMarkup()
        for group in groups:
            if str(group['group_id']) in APPROVED_GROUP_IDS:
                markup.add(InlineKeyboardButton(
                    f"المجموعة {group['group_id']}",
                    callback_data=f"group_{group['group_id']}")
                )
        
        bot.reply_to(message, "اختر المجموعة لعرض الأكواد والروابط:", reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ: {str(e)}")
        logger.error(f"خطأ في عرض الأكواد والروابط: {str(e)}")

def show_group_links(message, group_id):
    """عرض روابط وأكواد مجموعة محددة"""
    if str(group_id) not in APPROVED_GROUP_IDS:
        bot.reply_to(message, f"المجموعة {group_id} غير معتمدة.")
        return
    
    try:
        used_codes = db_manager.execute_query(
            """SELECT code, user_id, created_at 
            FROM codes 
            WHERE group_id = ? AND used = 1
            ORDER BY created_at DESC""",
            (group_id,),
            fetch=True
        )
        
        unused_codes = db_manager.execute_query(
            """SELECT code, created_at 
            FROM codes 
            WHERE group_id = ? AND used = 0
            ORDER BY created_at DESC""",
            (group_id,),
            fetch=True
        )
        
        invite_links = InviteManager.get_invite_links(db_manager, group_id)
        
        msg = f"معلومات المجموعة {group_id}:\n\n"
        
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
        msg += "\n\n"
        
        msg += "🔗 روابط الدعوة:\n"
        if invite_links:
            for link in invite_links:
                status = "🟢 صالح" if datetime.now().timestamp() < link['expire_time'] and not link['used'] else "🔴 منتهي"
                expire_time = datetime.fromtimestamp(link['expire_time']).strftime('%Y-%m-%d %H:%M:%S')
                msg += (f"- الرابط: {link['link']}\n"
                       f"  الكود: {link['code']}\n"
                       f"  المستخدم: {link['user_id']}\n"
                       f"  الحالة: {status}\n"
                       f"  الإنتهاء: {expire_time}\n\n")
        else:
            msg += "لا توجد روابط دعوة"
        
        bot.reply_to(message, msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ: {str(e)}")
        logger.error(f"خطأ في عرض معلومات المجموعة: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip().upper()
    user_id = message.from_user.id
    username = message.from_user.first_name or "عضو جديد"
    logger.info(f"الكود المدخل من المستخدم {user_id}: {code}")
    
    success, result = MembershipManager.process_code(bot, db_manager, user_id, code)
    
    if success:
        bot.reply_to(message, 
                    f"مرحبًا {username}!\n\n"
                    f"رابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة):\n{result}\n\n"
                    "سيتم إنهاء عضويتك بعد شهر تلقائيًا.")
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
        if message.chat.type in ['group', 'supergroup']:
            group_id = str(message.chat.id)
            welcome_msg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        else:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                bot.reply_to(message, 
                            "يرجى إدخال معرف المجموعة ورسالة الترحيب!\n"
                            "مثال: /set_welcome -1002329495586 🎉 مرحبًا بك، {username}!\n"
                            "📅 عضويتك ستنتهي بعد شهر.\n📜 يرجى الالتزام بقواعد المجموعة.\n"
                            "يمكن استخدام {username} لاستبدال اسم العضو تلقائيًا.")
                return
            group_id, welcome_msg = parts[1], parts[2]
        
        if str(group_id) not in APPROVED_GROUP_IDS:
            bot.reply_to(message, f"المجموعة {group_id} غير معتمدة. أضفها إلى القائمة المعتمدة أولاً.")
            return
        
        if not welcome_msg:
            bot.reply_to(message, "يرجى إدخال نص الرسالة الترحيبية!")
            return
        
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message) VALUES (?, ?)",
            (group_id, welcome_msg)
        )
        bot.reply_to(message, f"تم تحديث رسالة الترحيب للمجموعة {group_id} بنجاح!")
        logger.info(f"تم تحديث رسالة الترحيب للمجموعة {group_id} إلى: {welcome_msg}")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}\nاستخدم:\n- داخل المجموعة: /set_welcome <رسالة الترحيب>\n- خارج المجموعة: /set_welcome <group_id> <رسالة الترحيب>")
        logger.error(f"خطأ في تعيين رسالة الترحيب: {str(e)}")

# معالج للعضوية الجديدة
@bot.chat_member_handler()
def handle_new_member(update):
    """معالجة العضو الجديد عند الانضمام"""
    try:
        if update.new_chat_member.status == 'member':
            chat_id = update.chat.id
            user_id = update.new_chat_member.user.id
            
            if str(chat_id) not in APPROVED_GROUP_IDS:
                logger.warning(f"محاولة معالجة عضوية في مجموعة غير معتمدة: {chat_id}")
                return
            
            invite_link = getattr(update, 'invite_link', None)
            if invite_link:
                result = db_manager.execute_query(
                    "SELECT code, user_id FROM invite_links WHERE link = ? AND used = 0",
                    (invite_link.invite_link,),
                    fetch=True
                )
                if result:
                    code = result[0]['code']
                    link_user_id = result[0]['user_id']
                    if link_user_id == user_id:
                        db_manager.execute_query(
                            "UPDATE codes SET used = 1 WHERE code = ?",
                            (code,)
                        )
                        db_manager.execute_query(
                            "UPDATE invite_links SET used = 1 WHERE link = ?",
                            (invite_link.invite_link,)
                        )
                        logger.info(f"تم استخدام الكود {code} ورابط الدعوة بواسطة العضو {user_id}")
            
            # إرسال الرسالة الترحيبية فور الانضمام
            MembershipManager.send_welcome_message(bot, db_manager, chat_id, user_id)
            
    except Exception as e:
        logger.error(f"خطأ في معالجة العضو الجديد: {str(e)}")

# ===== الوظائف الخلفية =====

def check_expired_links_and_memberships():
    """فحص الروابط والعضويات المنتهية الصلاحية"""
    while True:
        try:
            now = datetime.now()
            
            expired_links = db_manager.execute_query(
                "SELECT link FROM invite_links WHERE expire_time < ? AND used = 0",
                (int(now.timestamp()),),
                fetch=True
            )
            
            for link in expired_links:
                db_manager.execute_query(
                    "UPDATE invite_links SET used = 1 WHERE link = ?",
                    (link['link'],)
                )
                logger.info(f"تم تعليم رابط الدعوة {link['link']} كمنتهي")
            
            expired_members = db_manager.execute_query(
                "SELECT user_id, group_id FROM memberships WHERE join_date < ?",
                ((now - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for member in expired_members:
                if str(member['group_id']) not in APPROVED_GROUP_IDS:
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
            
            time.sleep(3600)
            
        except Exception as e:
            logger.error(f"خطأ في الفحص الخلفي: {str(e)}")
            time.sleep(3600)

# بدء البوت
if __name__ == '__main__':
    try:
        bg_thread = threading.Thread(target=check_expired_links_and_memberships, daemon=True)
        bg_thread.start()
        
        logger.info("جاري تشغيل البوت...")
        retry_delay = 5
        while True:
            try:
                bot.infinity_polling()
            except Exception as e:
                logger.error(f"خطأ في التشغيل: {str(e)}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)
    except KeyboardInterrupt:
        logger.info("إيقاف البوت...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
        sys.exit(1)
