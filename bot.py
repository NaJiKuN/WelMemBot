# G1.1 - Welcome Message Update
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
import requests # Added for specific exception handling

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0' # استبدل هذا بالتوكن الخاص بك
ADMIN_ID = 764559466 # استبدل هذا بمعرف الأدمن الخاص بك
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db' # أو مسار مناسب لك
LOG_FILE = '/home/ec2-user/projects/WelMemBot/bot.log' # أو مسار مناسب لك

# قائمة المجموعات المعتمدة - هام: يجب أن يكون معرف المجموعة هنا كسلسلة نصية
APPROVED_GROUP_IDS = ['-1002329495586'] # استبدل هذا بمعرفات المجموعات المعتمدة

# الرسالة الترحيبية الافتراضية الجديدة
DEFAULT_WELCOME_MESSAGE_TEMPLATE = (
    "🎉 مرحبًا بك، {username} معنا!\n"
    "📅 عضويتك ستنتهي بعد شهر تلقائياً.\n"
    "📜 يرجى الالتزام بقواعد المجموعة."
)

# إعداد التسجيل (Logging)
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', # Added %(name)s for logger identification
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
bot = telebot.TeleBot(TOKEN, num_threads=5)

class DatabaseManager:
    """فئة لإدارة عمليات قاعدة البيانات"""
    def __init__(self, db_path):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"تم إنشاء مجلد قاعدة البيانات: {db_dir}")
        self._init_db()
        self._setup_default_groups()
    
    def _init_db(self):
        """تهيئة قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS codes
                             (code TEXT PRIMARY KEY, group_id TEXT, used INTEGER DEFAULT 0,
                              user_id INTEGER DEFAULT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
                c.execute('''CREATE TABLE IF NOT EXISTS memberships
                             (user_id INTEGER, group_id TEXT, join_date TEXT, 
                              notified INTEGER DEFAULT 0, PRIMARY KEY (user_id, group_id))''')
                c.execute('''CREATE TABLE IF NOT EXISTS groups
                             (group_id TEXT PRIMARY KEY, welcome_message TEXT, is_private INTEGER DEFAULT 0)''')
                c.execute('''CREATE TABLE IF NOT EXISTS invite_links
                             (link TEXT PRIMARY KEY, group_id TEXT, user_id INTEGER, code TEXT,
                              created_time TEXT, expire_time INTEGER, used INTEGER DEFAULT 0)''')
                conn.commit()
            logger.info("تم تهيئة قاعدة البيانات بنجاح")
        except Exception as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {str(e)}", exc_info=True)
            raise
    
    def _setup_default_groups(self):
        """إعداد المجموعات المعتمدة مسبقًا برسالة الترحيب الافتراضية الجديدة"""
        try:
            for group_id in APPROVED_GROUP_IDS:
                self.execute_query(
                    "INSERT OR IGNORE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
                    (group_id, DEFAULT_WELCOME_MESSAGE_TEMPLATE, 1) # استخدام الرسالة الجديدة
                )
            logger.info("تم إعداد المجموعات المعتمدة مسبقًا (إذا لم تكن موجودة) بنجاح")
        except Exception as e:
            logger.error(f"خطأ في إعداد المجموعات المعتمدة: {str(e)}", exc_info=True)
    
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
            logger.error(f"خطأ في تنفيذ الاستعلام '{query[:50]}...': {str(e)}", exc_info=True)
            raise

class BotPermissions:
    """فئة للتحقق من صلاحيات البوت"""
    @staticmethod
    def check_bot_permissions(bot_instance, chat_id):
        """التحقق من صلاحيات البوت في المجموعة"""
        try:
            str_chat_id = str(chat_id)
            if str_chat_id not in APPROVED_GROUP_IDS:
                logger.warning(f"المجموعة {chat_id} غير معتمدة")
                return False, "هذه المجموعة غير معتمدة. تواصل مع المسؤول للاعتماد."
            
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            
            can_invite_users = getattr(bot_member, 'can_invite_users', False)
            can_restrict_members = getattr(bot_member, 'can_restrict_members', False)
            can_send_messages = getattr(bot_member, 'can_send_messages', False)

            required_permissions_status = {
                'can_invite_users': can_invite_users,
                'can_restrict_members': can_restrict_members,
                'can_send_messages': can_send_messages,
                'status': bot_member.status
            }
            
            logger.info(f"صلاحيات البوت في المجموعة {chat_id}: {required_permissions_status}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logger.warning(f"البوت ليس مشرفًا في المجموعة {chat_id}")
                return False, "البوت يجب أن يكون مشرفاً في المجموعة"
                
            missing_permissions = []
            if not can_invite_users:
                missing_permissions.append("إضافة أعضاء (دعوة مستخدمين عبر رابط)")
            if not can_restrict_members:
                missing_permissions.append("حظر أعضاء")
            if not can_send_messages:
                missing_permissions.append("إرسال الرسائل")
                
            if missing_permissions:
                error_msg = f"البوت يحتاج الصلاحيات التالية: {', '.join(missing_permissions)}"
                logger.warning(error_msg)
                return False, error_msg
                
            return True, "الصلاحيات كافية"
            
        except telebot.apihelper.ApiTelegramException as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg:
                return False, "المجموعة غير موجودة أو المعرف خاطئ."
            elif "bot is not a member" in error_msg:
                return False, "البوت ليس عضواً في المجموعة."
            elif "user_not_participant" in error_msg or "member list is inaccessible" in error_msg:
                 return False, "البوت ليس لديه الصلاحية الكافية للوصول لمعلومات الأعضاء (قد لا يكون مشرفًا أو لا يملك صلاحية كافية)."
            logger.error(f"خطأ في API تيليجرام أثناء التحقق من الصلاحيات للمجموعة {chat_id}: {str(e)}", exc_info=True)
            return False, f"خطأ في API تيليجرام: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع في التحقق من الصلاحيات للمجموعة {chat_id}: {str(e)}", exc_info=True)
            return False, f"خطأ غير متوقع: {str(e)}"

class CodeGenerator:
    """فئة لتوليد وإدارة الأكواد"""
    @staticmethod
    def generate_code(length=8):
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_multiple_codes(db_manager, group_id, count):
        if str(group_id) not in APPROVED_GROUP_IDS:
            logger.error(f"محاولة توليد أكواد لمجموعة غير معتمدة: {group_id}")
            return []
        
        codes = []
        attempts = 0
        max_attempts = count * 3 # زيادة عدد المحاولات قليلاً
        while len(codes) < count and attempts < max_attempts:
            code = CodeGenerator.generate_code()
            try:
                db_manager.execute_query("INSERT INTO codes (code, group_id) VALUES (?, ?)", (code, group_id))
                codes.append(code)
            except sqlite3.IntegrityError:
                attempts += 1
                logger.warning(f"تضارب في الكود {code} (المحاولة {attempts}/{max_attempts})، محاولة مرة أخرى.")
                continue
            except Exception as e:
                logger.error(f"خطأ عند إدخال الكود {code} في قاعدة البيانات: {e}", exc_info=True)
                attempts +=1 
        if attempts >= max_attempts and len(codes) < count:
            logger.warning(f"تجاوز عدد المحاولات لتوليد الأكواد للمجموعة {group_id}. تم توليد {len(codes)} من {count} أكواد.")
        return codes

class InviteManager:
    """فئة لإدارة روابط الدعوة"""
    @staticmethod
    def create_invite_link(bot_instance, group_id, user_id, code):
        if str(group_id) not in APPROVED_GROUP_IDS:
            logger.error(f"محاولة إنشاء رابط دعوة لمجموعة غير معتمدة: {group_id}")
            return None, None, "المجموعة غير معتمدة"
        
        try:
            logger.info(f"محاولة إنشاء رابط دعوة للمجموعة {group_id} للمستخدم {user_id} (كود: {code})")
            expire_date = int(time.time()) + (24 * 60 * 60) 
            link_name = f"Inv_{code[:6]}_{user_id % 10000}" # اسم أقصر وأكثر تميزًا قليلاً
            link = bot_instance.create_chat_invite_link(
                chat_id=group_id, name=link_name, expire_date=expire_date, member_limit=1
            )
            logger.info(f"تم إنشاء رابط الدعوة بنجاح: {link.invite_link}")
            return link.invite_link, expire_date, None
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"خطأ في API تيليجرام أثناء إنشاء رابط الدعوة للمجموعة {group_id}: {str(e)}", exc_info=True)
            error_msg_lower = str(e).lower()
            if any(s in error_msg_lower for s in ["need administrator rights", "not enough rights", "chat admin required"]):
                return None, None, "البوت يحتاج صلاحية 'دعوة مستخدمين عبر رابط' (can_invite_users) لإنشاء رابط دعوة. تأكد أنه مشرف بهذه الصلاحية."
            elif "privacy settings" in error_msg_lower:
                return None, None, "يرجى التحقق من إعدادات الخصوصية للبوت في @BotFather. قد تحتاج لتعطيل وضع الخصوصية باستخدام /setprivacy -> Disable."
            elif "chat not found" in error_msg_lower:
                return None, None, "المجموعة غير موجودة أو المعرف غير صحيح."
            elif "bot is not a member" in error_msg_lower:
                return None, None, "البوت ليس عضواً في المجموعة."
            return None, None, f"خطأ في API تيليجرام عند إنشاء الرابط: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع أثناء إنشاء رابط الدعوة للمجموعة {group_id}: {str(e)}", exc_info=True)
            return None, None, f"خطأ غير متوقع عند إنشاء الرابط: {str(e)}"
    
    @staticmethod
    def store_invite_link(db_manager, link_data):
        try:
            db_manager.execute_query(
                "INSERT INTO invite_links (link, group_id, user_id, code, created_time, expire_time) VALUES (?, ?, ?, ?, ?, ?)",
                link_data
            )
            logger.info(f"تم تخزين رابط الدعوة بنجاح: {link_data[0]}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تخزين رابط الدعوة {link_data[0]}: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def get_invite_links(db_manager, group_id=None):
        try:
            query = "SELECT * FROM invite_links"
            params = []
            if group_id:
                query += " WHERE group_id = ?"
                params.append(group_id)
            query += " ORDER BY created_time DESC"
            return db_manager.execute_query(query, tuple(params), fetch=True)
        except Exception as e:
            logger.error(f"خطأ في جلب روابط الدعوة: {str(e)}", exc_info=True)
            return None

class MembershipManager:
    """فئة لإدارة العضويات"""
    @staticmethod
    def process_code(bot_instance, db_manager, user_id, code):
        try:
            logger.info(f"معالجة الكود {code} للمستخدم {user_id}")
            code_data = db_manager.execute_query(
                "SELECT group_id FROM codes WHERE code = ? AND used = 0", (code,), fetch=True
            )
            
            if not code_data:
                logger.warning(f"الكود {code} غير صالح أو مستخدم من قبل.")
                return False, "الكود غير صالح أو مستخدم من قبل."
            
            group_id = code_data[0]['group_id']
            if str(group_id) not in APPROVED_GROUP_IDS:
                logger.error(f"محاولة معالجة كود لمجموعة غير معتمدة: {group_id} (الكود: {code})")
                return False, "هذا الكود مخصص لمجموعة غير مدعومة حاليًا. تواصل مع المسؤول."
            
            logger.info(f"الكود {code} مرتبط بالمجموعة {group_id}")
            
            try:
                member = bot_instance.get_chat_member(group_id, user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    logger.info(f"المستخدم {user_id} بالفعل عضو في المجموعة {group_id}")
                    return False, "أنت بالفعل عضو في المجموعة!"
            except telebot.apihelper.ApiTelegramException as e:
                if not ("user not found" in str(e).lower() or "user_not_participant" in str(e).lower()):
                    logger.error(f"خطأ في التحقق من حالة العضوية لـ {user_id} في {group_id}: {str(e)}", exc_info=True)
                    return False, f"خطأ في التحقق من حالة عضويتك: {str(e)}"
            
            perm_success, perm_msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not perm_success:
                logger.warning(f"فشل التحقق من صلاحيات البوت للمجموعة {group_id} (كود {code}): {perm_msg}")
                bot_instance.send_message(ADMIN_ID, 
                    f"تنبيه: فشل التحقق من صلاحيات البوت في المجموعة {group_id} عند محاولة المستخدم {user_id} استخدام الكود {code}.\n"
                    f"السبب: {perm_msg}\nيرجى مراجعة صلاحيات البوت في تلك المجموعة.")
                return False, f"حدث خطأ إداري يمنع إنشاء رابط الدعوة حاليًا. ({perm_msg})"
            
            invite_link, expire_time, error_msg_link = InviteManager.create_invite_link(
                bot_instance, group_id, user_id, code)
            
            if not invite_link:
                logger.error(f"فشل في إنشاء رابط الدعوة للمستخدم {user_id} للكود {code}: {error_msg_link}")
                bot_instance.send_message(ADMIN_ID, 
                    f"تنبيه: فشل إنشاء رابط دعوة للمستخدم {user_id} (كود: {code}) للمجموعة {group_id}.\n"
                    f"السبب: {error_msg_link}")
                return False, error_msg_link or "فشل في إنشاء رابط الدعوة. تم إبلاغ المسؤول."
            
            link_data_tuple = (invite_link, group_id, user_id, code, datetime.now().isoformat(), expire_time)
            InviteManager.store_invite_link(db_manager, link_data_tuple) # Log error inside if fails
            
            db_manager.execute_query("UPDATE codes SET user_id = ?, used = 1 WHERE code = ?", (user_id, code))
            logger.info(f"تم تحديث الكود {code} كمستخدم (رابط أُنشئ) بواسطة {user_id}")
            
            return True, invite_link
            
        except Exception as e:
            logger.error(f"خطأ عام في معالجة الكود {code} للمستخدم {user_id}: {str(e)}", exc_info=True)
            return False, "حدث خطأ غير متوقع أثناء معالجة الكود. يرجى المحاولة مرة أخرى لاحقًا أو التواصل مع المسؤول."

    @staticmethod
    def send_welcome_message(bot_instance, db_manager, chat_id, user_id):
        try:
            str_chat_id = str(chat_id)
            if str_chat_id not in APPROVED_GROUP_IDS:
                logger.warning(f"محاولة إرسال رسالة ترحيب لمجموعة غير معتمدة: {chat_id}")
                return False
            
            user_info = bot_instance.get_chat(user_id)
            username = user_info.first_name or user_info.username or f"User_{user_id}"
            
            welcome_result = db_manager.execute_query(
                "SELECT welcome_message FROM groups WHERE group_id = ?", (str_chat_id,), fetch=True
            )
            
            # استخدام DEFAULT_WELCOME_MESSAGE_TEMPLATE المحدثة كقيمة افتراضية
            welcome_msg_template = (welcome_result[0]['welcome_message'] 
                                    if welcome_result and welcome_result[0]['welcome_message'] 
                                    else DEFAULT_WELCOME_MESSAGE_TEMPLATE)
            
            welcome_msg = welcome_msg_template.format(username=telebot.util.escape(username))
            
            current_time_iso = datetime.now().isoformat()
            db_manager.execute_query(
                "INSERT INTO memberships (user_id, group_id, join_date, notified) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(user_id, group_id) DO UPDATE SET join_date = excluded.join_date, notified = 0",
                (user_id, str_chat_id, current_time_iso)
            )
            logger.info(f"تم تسجيل/تحديث عضوية للمستخدم {user_id} في المجموعة {chat_id}")

            try:
                bot_instance.send_message(chat_id, welcome_msg, parse_mode='Markdown')
                logger.info(f"تم إرسال رسالة الترحيب إلى المجموعة {chat_id} للمستخدم {user_id}")
            except telebot.apihelper.ApiTelegramException as e_send:
                if any(s in str(e_send).lower() for s in ["can't send messages", "bot is not a member", "chat not found"]):
                    bot_instance.send_message(ADMIN_ID, 
                        f"تنبيه: لم أتمكن من إرسال رسالة الترحيب في المجموعة {chat_id} (المستخدم: {username}, ID: {user_id}).\n"
                        f"السبب المحتمل: {str(e_send)}\nالرسالة كانت:\n{welcome_msg}")
                    logger.warning(f"لا يمكن إرسال رسائل في المجموعة {chat_id}. تم إرسال رسالة الترحيب إلى الأدمن. الخطأ: {e_send}")
                else:
                    raise e_send 
            return True
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة الترحيب للمستخدم {user_id} في المجموعة {chat_id}: {str(e)}", exc_info=True)
            try:
                bot_instance.send_message(ADMIN_ID, f"فشل إرسال رسالة الترحيب للمستخدم {user_id} في المجموعة {chat_id}.\nالخطأ: {str(e)}")
            except Exception as admin_notify_err:
                logger.error(f"فشل إضافي في إبلاغ الأدمن بخطأ رسالة الترحيب: {admin_notify_err}", exc_info=True)
            return False
    
    @staticmethod
    def notify_expired_memberships(bot_instance, db_manager):
        try:
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            expired_members = db_manager.execute_query(
                "SELECT user_id, group_id, join_date FROM memberships WHERE join_date < ? AND notified = 0",
                (thirty_days_ago,), fetch=True
            )
            
            for member in expired_members:
                group_id_str = str(member['group_id'])
                if group_id_str not in APPROVED_GROUP_IDS:
                    logger.warning(f"تجاهل إشعار انتهاء عضوية لمجموعة غير معتمدة: {group_id_str}")
                    continue
                
                try:
                    user_info = bot_instance.get_chat(member['user_id'])
                    username = user_info.first_name or user_info.username or f"User_{member['user_id']}"
                    join_date_dt = datetime.fromisoformat(member['join_date'])
                    expiry_date_dt = join_date_dt + timedelta(days=30)
                    
                    admin_message = (
                        f"🔔 *إشعار انتهاء عضوية*\n\n"
                        f"العضو: {telebot.util.escape(username)} (ID: `{member['user_id']}`)\n"
                        f"المجموعة: `{member['group_id']}`\n"
                        f"تاريخ الانضمام: {join_date_dt.strftime('%Y-%m-%d %H:%M')}\n"
                        f"تاريخ انتهاء العضوية (متوقع): {expiry_date_dt.strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"الإجراء المقترح: التحقق من حالة العضو وطرده إذا لزم الأمر (الطرد التلقائي مفعل)."
                    )
                    bot_instance.send_message(ADMIN_ID, admin_message, parse_mode='Markdown')
                    
                    db_manager.execute_query(
                        "UPDATE memberships SET notified = 1 WHERE user_id = ? AND group_id = ?",
                        (member['user_id'], member['group_id'])
                    )
                    logger.info(f"تم إرسال إشعار للأدمن عن انتهاء عضوية {member['user_id']} في المجموعة {member['group_id']}")
                    
                except telebot.apihelper.ApiTelegramException as e_api_notify:
                    if "user not found" in str(e_api_notify).lower():
                        logger.warning(f"المستخدم {member['user_id']} لم يعد موجودًا عند إشعار انتهاء العضوية. سيتم تحديث notified=1.")
                        db_manager.execute_query("UPDATE memberships SET notified = 1 WHERE user_id = ? AND group_id = ?", (member['user_id'], member['group_id']))
                    else:
                        logger.error(f"خطأ API أثناء إرسال إشعار انتهاء العضوية للمسؤول عن {member['user_id']}: {str(e_api_notify)}", exc_info=True)
                except Exception as e_inner_notify:
                    logger.error(f"خطأ غير متوقع أثناء معالجة إشعار انتهاء عضوية {member['user_id']}: {str(e_inner_notify)}", exc_info=True)
            return True
        except Exception as e_notify_main:
            logger.error(f"خطأ عام في وظيفة إشعارات العضويات المنتهية: {str(e_notify_main)}", exc_info=True)
            return False

db_manager = DatabaseManager(DB_PATH)

@bot.message_handler(commands=['start', 'help'])
def start_command(message): # Renamed for clarity
    user_id = message.from_user.id
    username_log = message.from_user.username or message.from_user.first_name
    logger.info(f"أمر /start أو /help من المستخدم {user_id} ({username_log})")
    
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("⚙️ إنشاء أكواد جديدة", callback_data="admin_generate_codes"))
        markup.add(InlineKeyboardButton("📊 عرض الأكواد والروابط", callback_data="admin_show_links"))
        markup.add(InlineKeyboardButton("💬 تعديل رسالة الترحيب", callback_data="admin_set_welcome"))
        
        bot.reply_to(message, "أهلاً بك أيها الأدمن! 👋\nاختر الإجراء المطلوب من القائمة:", reply_markup=markup)
    else:
        bot.reply_to(message, 
                     "مرحبًا بك! 👋\n"
                     "إذا كان لديك كود للانضمام إلى إحدى المجموعات، يرجى إرساله الآن.")
        bot.register_next_step_handler(message, handle_user_code_submission) # Renamed

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID) # Only admin can use callbacks
def handle_admin_callback(call): # Renamed
    try:
        bot.answer_callback_query(call.id) 
        action = call.data.split("_", 1)[1] # Remove "admin_" prefix
        
        if action == "generate_codes":
            bot.send_message(call.message.chat.id, "يرجى إدخال معرف المجموعة (Group ID) التي تريد إنشاء أكواد لها:")
            bot.register_next_step_handler(call.message, get_group_id_for_admin_code_generation) # Renamed
        elif action == "show_links":
            show_admin_group_links_options(call.message) # Renamed
        elif action.startswith("group_links_"): # e.g., admin_group_links_-100123
            group_id = action.split("_")[2] # Get the ID part
            show_specific_group_data_to_admin(call.message, group_id) # Renamed
        elif action == "set_welcome":
            bot.send_message(call.message.chat.id, 
                             "لتعديل رسالة الترحيب، أرسل الأمر التالي:\n"
                             "`/set_welcome GROUP_ID رسالتك هنا`\n\n"
                             "مثال:\n"
                             f"`/set_welcome -1001234567890 {DEFAULT_WELCOME_MESSAGE_TEMPLATE.splitlines()[0]}`\n" # Show example with new default
                             "تذكر أن `{username}` سيتم استبداله باسم العضو.\n"
                             "إذا كنت داخل المجموعة وتريد تعيين رسالتها، يمكنك استخدام:\n"
                             "`/set_welcome رسالتك هنا`")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار (callback_query) للأدمن: {str(e)}", exc_info=True)
        try:
            bot.edit_message_text("حدث خطأ ما، يرجى المحاولة لاحقًا.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass # Ignore if edit fails

@bot.callback_query_handler(func=lambda call: call.from_user.id != ADMIN_ID)
def handle_non_admin_callback(call):
    bot.answer_callback_query(call.id, "⚠️ هذا الإجراء مخصص للأدمن فقط!", show_alert=True)


def handle_user_code_submission(message): # Renamed
    code_text = message.text.strip().upper()
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "عضو جديد"
    username_log = message.from_user.username or first_name

    logger.info(f"الكود المدخل من المستخدم {user_id} ({username_log}): {code_text}")
    
    success, result_or_msg = MembershipManager.process_code(bot, db_manager, user_id, code_text)
    
    if success: 
        bot.reply_to(message, 
                     f"مرحبًا {telebot.util.escape(first_name)}!\n\n"
                     f"✅ تم التحقق من الكود بنجاح.\n"
                     f"إليك رابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة ولمستخدم واحد فقط):\n"
                     f"{result_or_msg}\n\n"
                     "⚠️ عضويتك في المجموعة ستكون لمدة شهر واحد، وبعدها قد يتم إزالتك تلقائيًا.\n"
                     "يرجى الالتزام بقوانين المجموعة.", 
                     parse_mode='Markdown')
        logger.info(f"تم إرسال رابط الدعوة {result_or_msg} للمستخدم {user_id} ({username_log}) للكود {code_text}")
    else: 
        bot.reply_to(message, 
                     f"عذرًا {telebot.util.escape(first_name)}، حدث خطأ:\n\n"
                     f"🚫 {telebot.util.escape(result_or_msg)}\n\n"
                     "يرجى التأكد من صحة الكود والمحاولة مرة أخرى، أو التواصل مع المسؤول إذا استمرت المشكلة.")
        logger.warning(f"فشل في معالجة الكود {code_text} للمستخدم {user_id} ({username_log}): {result_or_msg}")


def get_group_id_for_admin_code_generation(message): # Renamed
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    group_id_input = message.text.strip()
    logger.info(f"الأدمن أدخل معرف المجموعة لإنشاء الأكواد: {group_id_input}")
    
    try:
        if not (group_id_input.startswith('-') and group_id_input[1:].isdigit()):
            bot.reply_to(message, "⚠️ معرف المجموعة غير صالح! يجب أن يكون رقمًا سالبًا (مثال: -1001234567890).")
            return
        
        if group_id_input not in APPROVED_GROUP_IDS:
            bot.reply_to(message, f"⚠️ المجموعة ذات المعرف {group_id_input} غير موجودة في قائمة المجموعات المعتمدة.\n"
                                  f"يرجى إضافتها إلى `APPROVED_GROUP_IDS` في الكود أولاً أو التأكد من صحة المعرف.")
            return
        
        chat_info = bot.get_chat(group_id_input)
        
        perm_success, perm_msg = BotPermissions.check_bot_permissions(bot, group_id_input)
        if not perm_success:
            bot.reply_to(message, f"❌ خطأ في صلاحيات البوت للمجموعة {chat_info.title} ({group_id_input}):\n{perm_msg}\n\n"
                                  "يرجى منح البوت الصلاحيات المطلوبة في تلك المجموعة ثم المحاولة مرة أخرى.")
            return
        
        group_exists_in_db = db_manager.execute_query("SELECT 1 FROM groups WHERE group_id = ?", (group_id_input,), fetch=True)
        if not group_exists_in_db:
             # استخدام DEFAULT_WELCOME_MESSAGE_TEMPLATE المحدثة
            db_manager.execute_query(
                "INSERT OR IGNORE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
                (group_id_input, DEFAULT_WELCOME_MESSAGE_TEMPLATE, 1 if chat_info.type in ['group', 'supergroup'] else 0)
            )
            logger.info(f"تم إضافة المجموعة {group_id_input} إلى جدول groups تلقائيًا بالرسالة الافتراضية المحدثة.")

        bot.reply_to(message, f"✅ تم تحديد المجموعة بنجاح: {chat_info.title} (ID: {group_id_input}).\n"
                              "الآن، أدخل عدد الأكواد التي ترغب في إنشائها لهذه المجموعة (مثال: 10):")
        bot.register_next_step_handler(message, lambda m: generate_new_codes_for_admin(m, group_id_input)) # Renamed
        
    except telebot.apihelper.ApiTelegramException as e_api_group:
        if "chat not found" in str(e_api_group).lower():
            bot.reply_to(message, f"❌ لم أتمكن من العثور على مجموعة بالمعرف {group_id_input}. يرجى التأكد من صحة المعرف وأن البوت عضو فيها.")
        else:
            bot.reply_to(message, f"❌ خطأ في API تيليجرام عند محاولة الوصول للمجموعة {group_id_input}: {str(e_api_group)}")
        logger.error(f"خطأ API في get_group_id_for_admin_code_generation للمجموعة {group_id_input}: {str(e_api_group)}", exc_info=True)
    except Exception as e_group_gen:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع: {str(e_group_gen)}")
        logger.error(f"خطأ عام في get_group_id_for_admin_code_generation للمجموعة {group_id_input}: {str(e_group_gen)}", exc_info=True)

def generate_new_codes_for_admin(message, group_id): # Renamed
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    if str(group_id) not in APPROVED_GROUP_IDS:
        bot.reply_to(message, f"⚠️ المجموعة {group_id} غير معتمدة. هذا غير متوقع.")
        logger.error(f"محاولة توليد أكواد لمجموعة {group_id} غير معتمدة داخل generate_new_codes_for_admin.")
        return
    
    try:
        num_codes_str = message.text.strip()
        if not num_codes_str.isdigit() or int(num_codes_str) <= 0:
            bot.reply_to(message, "⚠️ يرجى إدخال عدد صحيح موجب للأكواد (مثال: 5). أعد المحاولة:")
            bot.register_next_step_handler(message, lambda m: generate_new_codes_for_admin(m, group_id))
            return
        
        num_codes = int(num_codes_str)
        if num_codes > 100: 
             bot.reply_to(message, "⚠️ لا يمكن إنشاء أكثر من 100 كود في المرة الواحدة. أدخل عدد أقل:")
             bot.register_next_step_handler(message, lambda m: generate_new_codes_for_admin(m, group_id))
             return

        generated_codes = CodeGenerator.generate_multiple_codes(db_manager, group_id, num_codes)
        
        if not generated_codes:
            bot.reply_to(message, "⚠️ حدث خطأ أثناء توليد الأكواد أو لم يتم توليد أي أكواد. يرجى المحاولة مرة أخرى أو مراجعة السجلات.")
            return
            
        codes_str_list = [f"`{code}`" for code in generated_codes]
        
        base_reply_message = f"✅ تم بنجاح توليد {len(generated_codes)} كود/أكواد جديدة للمجموعة `{group_id}`:\n\n"
        
        current_batch_msg = base_reply_message
        for i, code_md in enumerate(codes_str_list):
            if len(current_batch_msg + code_md + "\n") > 4000: 
                bot.send_message(message.chat.id, current_batch_msg, parse_mode='Markdown')
                current_batch_msg = "" 
            current_batch_msg += code_md + "\n"
            if (i + 1) % 20 == 0 and i < len(codes_str_list) -1 : 
                current_batch_msg += "\n" # Add extra newline for readability between blocks of 20

        if current_batch_msg and current_batch_msg != base_reply_message : # Send remaining batch if it has codes
             bot.send_message(message.chat.id, current_batch_msg, parse_mode='Markdown')
        elif not generated_codes: # Should not happen if check above is fine, but as a safeguard
             bot.send_message(message.chat.id, base_reply_message + "لم يتم توليد أكواد.", parse_mode='Markdown')


        bot.send_message(message.chat.id, "يمكنك نسخ الأكواد من الأعلى ومشاركتها مع الأعضاء.")
        logger.info(f"الأدمن {message.from_user.id} قام بتوليد {len(generated_codes)} أكواد للمجموعة {group_id}")
        
    except Exception as e_gen_codes:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع أثناء توليد الأكواد: {str(e_gen_codes)}")
        logger.error(f"خطأ في generate_new_codes_for_admin للمجموعة {group_id}: {str(e_gen_codes)}", exc_info=True)

def show_admin_group_links_options(message): # Renamed
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 هذا الإجراء مخصص للأدمن فقط.")
        return
        
    try:
        groups_from_db = db_manager.execute_query(
            "SELECT group_id FROM groups WHERE group_id IN ({seq})".format(
                seq=','.join(['?']*len(APPROVED_GROUP_IDS))),
            tuple(APPROVED_GROUP_IDS), fetch=True
        )
        
        if not groups_from_db:
            bot.reply_to(message, "ℹ️ لا توجد مجموعات معتمدة مسجلة في قاعدة البيانات حاليًا أو لم يتم إنشاء أكواد لأي منها بعد.")
            return
            
        markup = InlineKeyboardMarkup(row_width=1)
        found_displayable_groups = False
        for group_row in groups_from_db:
            group_id_val = group_row['group_id']
            group_title = group_id_val 
            try:
                chat_info = bot.get_chat(group_id_val)
                group_title = chat_info.title or group_id_val
            except Exception as e_chat_title:
                logger.warning(f"لم يتمكن من جلب اسم المجموعة {group_id_val}: {e_chat_title}")

            markup.add(InlineKeyboardButton(
                f"المجموعة: {group_title} ({group_id_val})", 
                callback_data=f"admin_group_links_{group_id_val}") # Keep admin_ prefix for callback handler
            )
            found_displayable_groups = True
        
        if not found_displayable_groups:
             bot.reply_to(message, "ℹ️ لم يتم العثور على مجموعات معتمدة لديها أكواد أو روابط لعرضها حاليًا.")
             return

        bot.edit_message_text("اختر المجموعة لعرض الأكواد والروابط الخاصة بها:", chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup)
    except Exception as e_show_options:
        bot.reply_to(message, f"❌ حدث خطأ أثناء محاولة عرض خيارات المجموعات: {str(e_show_options)}")
        logger.error(f"خطأ في show_admin_group_links_options: {str(e_show_options)}", exc_info=True)

def show_specific_group_data_to_admin(message, group_id): # Renamed
    if message.from_user.id != ADMIN_ID:
        bot.edit_message_text("🚫 هذا الإجراء مخصص للأدمن فقط.", chat_id=message.chat.id, message_id=message.message_id)
        return

    if str(group_id) not in APPROVED_GROUP_IDS:
        bot.edit_message_text(f"⚠️ المجموعة {group_id} غير معتمدة.", chat_id=message.chat.id, message_id=message.message_id)
        return
    
    try:
        group_title = group_id
        try:
            chat_info = bot.get_chat(group_id)
            group_title = chat_info.title or group_id
        except: pass

        used_codes_q = db_manager.execute_query(
            "SELECT code, user_id, strftime('%Y-%m-%d %H:%M', created_at) as ca_fmt FROM codes WHERE group_id = ? AND used = 1 ORDER BY created_at DESC LIMIT 20",
            (group_id,), fetch=True
        )
        unused_codes_q = db_manager.execute_query(
            "SELECT code, strftime('%Y-%m-%d %H:%M', created_at) as ca_fmt FROM codes WHERE group_id = ? AND used = 0 ORDER BY created_at DESC LIMIT 20",
            (group_id,), fetch=True
        )
        invite_links_q = InviteManager.get_invite_links(db_manager, group_id)
        
        response_msg = f"📊 *معلومات الأكواد والروابط للمجموعة: {telebot.util.escape(group_title)} ({group_id})*\n(يتم عرض أحدث 20 كود/10 روابط كحد أقصى)\n\n"
        
        response_msg += "🟢 *الأكواد غير المستخدمة:*\n"
        if unused_codes_q: response_msg += "\n".join([f"- `{c['code']}` (أنشئ: {c['ca_fmt']})" for c in unused_codes_q])
        else: response_msg += "لا توجد أكواد غير مستخدمة."
        response_msg += "\n\n"
        
        response_msg += "🔴 *الأكواد المستخدمة:*\n"
        if used_codes_q: response_msg += "\n".join([f"- `{c['code']}` (بواسطة: `{c['user_id'] or 'غير معروف'}` | أنشئ: {c['ca_fmt']})" for c in used_codes_q])
        else: response_msg += "لا توجد أكواد مستخدمة."
        response_msg += "\n\n"
        
        response_msg += "🔗 *روابط الدعوة (الأحدث أولاً):*\n"
        if invite_links_q:
            sorted_links = sorted(invite_links_q, key=lambda x: x['created_time'], reverse=True)[:10]
            for link_info in sorted_links:
                is_used = link_info['used'] == 1
                is_expired = datetime.now().timestamp() >= link_info['expire_time']
                status = "🔴 مستخدم" if is_used else ("⚠️ منتهي" if is_expired else "🟢 صالح")
                expire_dt = datetime.fromtimestamp(link_info['expire_time']).strftime('%Y-%m-%d %H:%M')
                created_dt = datetime.fromisoformat(link_info['created_time']).strftime('%Y-%m-%d %H:%M')
                response_msg += (f"— اللينك: `{link_info['link']}`\n"
                                 f"  الكود: `{link_info['code']}` | لـ ID: `{link_info['user_id'] or 'N/A'}`\n"
                                 f"  الحالة: *{status}* | أنشئ: {created_dt} | ينتهي: {expire_dt}\n\n")
        else: response_msg += "لا توجد روابط دعوة لهذه المجموعة."
        
        if len(response_msg) > 4096: response_msg = response_msg[:4090] + "\n(...)"
        bot.edit_message_text(response_msg, chat_id=message.chat.id, message_id=message.message_id, parse_mode='Markdown', disable_web_page_preview=True)

    except Exception as e_show_specific:
        error_text = f"❌ حدث خطأ أثناء عرض معلومات المجموعة {group_id}: {str(e_show_specific)}"
        logger.error(f"خطأ في show_specific_group_data_to_admin للمجموعة {group_id}: {str(e_show_specific)}", exc_info=True)
        try: bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=message.message_id)
        except: bot.send_message(message.chat.id, error_text)


@bot.message_handler(commands=['set_welcome'])
def set_custom_welcome_message(message): # Renamed
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    parts = message.text.split(maxsplit=1)
    target_group_id = ""
    welcome_text = ""

    if message.chat.type in ['group', 'supergroup']:
        target_group_id = str(message.chat.id)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ يرجى تحديد نص رسالة الترحيب بعد الأمر.\nمثال: `/set_welcome أهلاً بك {username}!`")
            return
        welcome_text = parts[1].strip()
    elif message.chat.type == 'private':
        private_parts = message.text.split(maxsplit=2)
        if len(private_parts) < 3 or not private_parts[1].strip() or not private_parts[2].strip():
            bot.reply_to(message, "⚠️ للاستخدام في الخاص، حدد ID المجموعة ثم رسالة الترحيب.\nمثال: `/set_welcome -100123 مرحباً {username}!`")
            return
        target_group_id = private_parts[1].strip()
        welcome_text = private_parts[2].strip()
    else:
        bot.reply_to(message, "لا يمكن استخدام هذا الأمر هنا.")
        return

    if target_group_id not in APPROVED_GROUP_IDS:
        bot.reply_to(message, f"⚠️ المجموعة {target_group_id} غير موجودة في قائمة المجموعات المعتمدة.")
        return
    
    if not (target_group_id.startswith('-') and target_group_id[1:].isdigit()):
        bot.reply_to(message, "⚠️ معرف المجموعة الذي أدخلته غير صالح.")
        return

    try:
        perm_success, perm_msg = BotPermissions.check_bot_permissions(bot, target_group_id)
        if not perm_success:
             bot.reply_to(message, f"❌ لا يمكن تعيين رسالة الترحيب للمجموعة {target_group_id}.\nالسبب: {perm_msg}")
             return

        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, COALESCE((SELECT is_private FROM groups WHERE group_id = ?), 1))",
            (target_group_id, welcome_text, target_group_id)
        )
        bot.reply_to(message, f"✅ تم تحديث رسالة الترحيب للمجموعة `{target_group_id}` إلى:\n\n`{telebot.util.escape(welcome_text)}`", parse_mode='Markdown')
        logger.info(f"الأدمن {message.from_user.id} حدث رسالة الترحيب للمجموعة {target_group_id} إلى: {welcome_text}")
    except telebot.apihelper.ApiTelegramException as e_api_set_welcome:
         bot.reply_to(message, f"❌ خطأ من تيليجرام عند محاولة الوصول للمجموعة {target_group_id}: {e_api_set_welcome}\nتأكد أن المعرف صحيح وأن البوت عضو ومشرف.")
         logger.error(f"خطأ API في set_custom_welcome_message للمجموعة {target_group_id}: {e_api_set_welcome}", exc_info=True)
    except Exception as e_set_welcome:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع: {str(e_set_welcome)}")
        logger.error(f"خطأ عام في set_custom_welcome_message للمجموعة {target_group_id}: {str(e_set_welcome)}", exc_info=True)


@bot.chat_member_handler()
def handle_group_member_updates(update: telebot.types.ChatMemberUpdated): # Renamed
    try:
        chat_id_str = str(update.chat.id)
        if chat_id_str not in APPROVED_GROUP_IDS:
            return

        user_id = update.new_chat_member.user.id
        user_name_log = update.new_chat_member.user.first_name or update.new_chat_member.user.username
        logger.info(f"تحديث عضوية في المجموعة {chat_id_str}: المستخدم {user_id} ({user_name_log}), "
                    f"الحالة القديمة: {update.old_chat_member.status}, الجديدة: {update.new_chat_member.status}")

        if update.new_chat_member.status == 'member' and \
           (update.old_chat_member.status in ['left', 'kicked', None] or not update.old_chat_member.status): # Check if user was not a member
            
            invite_link_obj = getattr(update, 'invite_link', None)
            if invite_link_obj and invite_link_obj.creator.id == bot.get_me().id:
                logger.info(f"العضو {user_id} انضم إلى {chat_id_str} عبر رابط البوت: {invite_link_obj.invite_link}")
                db_manager.execute_query("UPDATE invite_links SET used = 1 WHERE link = ?", (invite_link_obj.invite_link,))
                logger.info(f"تم تحديث رابط الدعوة {invite_link_obj.invite_link} كـ 'مستخدم'.")
            else:
                logger.info(f"العضو {user_id} انضم إلى المجموعة {chat_id_str} (ليس عبر رابط البوت أو الرابط غير متتبع).")
            
            MembershipManager.send_welcome_message(bot, db_manager, update.chat.id, user_id)
        
        elif update.new_chat_member.status in ['left', 'kicked']:
            logger.info(f"العضو {user_id} ({user_name_log}) غادر المجموعة {chat_id_str} أو تم طرده.")
            # Optionally, delete membership record upon leaving/kick
            # db_manager.execute_query("DELETE FROM memberships WHERE user_id = ? AND group_id = ?", (user_id, chat_id_str))

    except Exception as e_member_update:
        logger.error(f"خطأ في معالجة تحديث حالة العضو (handle_group_member_updates): {str(e_member_update)}", exc_info=True)


def scheduled_background_tasks(): # Renamed
    logger.info("بدء مؤشر ترابط المهام الخلفية المجدولة...")
    while True:
        try:
            logger.info("الدورة الخلفية: التحقق من الروابط والعضويات المنتهية...")
            now_timestamp = int(time.time())
            
            expired_links_to_mark = db_manager.execute_query(
                "SELECT link FROM invite_links WHERE expire_time < ? AND used = 0", (now_timestamp,), fetch=True
            )
            for link_row in expired_links_to_mark:
                db_manager.execute_query("UPDATE invite_links SET used = 1 WHERE link = ?", (link_row['link'],))
                logger.info(f"تم تعليم رابط الدعوة المنتهي الصلاحية {link_row['link']} كـ 'منتهي'.")
            
            thirty_days_ago_iso = (datetime.now() - timedelta(days=30)).isoformat()
            members_to_kick = db_manager.execute_query(
                "SELECT user_id, group_id FROM memberships WHERE join_date < ?", (thirty_days_ago_iso,), fetch=True
            )
            
            for member in members_to_kick:
                group_id_str = str(member['group_id'])
                if group_id_str not in APPROVED_GROUP_IDS:
                    logger.warning(f"تجاهل طرد عضو من مجموعة غير معتمدة: {group_id_str}, المستخدم: {member['user_id']}")
                    continue
                
                user_id_to_kick = member['user_id']
                
                try:
                    perm_success, perm_msg = BotPermissions.check_bot_permissions(bot, group_id_str)
                    if not perm_success or "حظر أعضاء" in perm_msg or not getattr(bot.get_chat_member(group_id_str, bot.get_me().id), 'can_restrict_members', False):
                        logger.warning(f"لا يمكن طرد العضو {user_id_to_kick} من {group_id_str} بسبب نقص صلاحية 'حظر أعضاء'.")
                        bot.send_message(ADMIN_ID, f"⚠️ لا يمكن طرد العضو {user_id_to_kick} من المجموعة {group_id_str} بسبب نقص صلاحية 'حظر أعضاء'. يرجى مراجعة صلاحيات البوت.")
                        continue 

                    bot.kick_chat_member(group_id_str, user_id_to_kick)
                    logger.info(f"تم طرد العضو {user_id_to_kick} من المجموعة {group_id_str} لانتهاء عضويته.")
                    
                    db_manager.execute_query("DELETE FROM memberships WHERE user_id = ? AND group_id = ?", (user_id_to_kick, group_id_str))
                    logger.info(f"تم حذف عضوية {user_id_to_kick} من {group_id_str} بعد الطرد.")

                    try:
                        user_info_kicked = bot.get_chat(user_id_to_kick) # Might fail if user deleted account
                        kicked_username = user_info_kicked.first_name or user_info_kicked.username or f"User_{user_id_to_kick}"
                        bot.send_message(ADMIN_ID, 
                                         f"🗑️ تم طرد العضو {telebot.util.escape(kicked_username)} (ID: `{user_id_to_kick}`) "
                                         f"من المجموعة `{group_id_str}` لانتهاء فترة عضويته.", parse_mode='Markdown')
                    except Exception as notify_err_kick:
                         logger.error(f"فشل إبلاغ الأدمن بطرد {user_id_to_kick}: {notify_err_kick}")

                except telebot.apihelper.ApiTelegramException as e_api_kick:
                    error_lower = str(e_api_kick).lower()
                    if "user not found" in error_lower or "user_not_participant" in error_lower:
                        logger.warning(f"العضو {user_id_to_kick} غير موجود في {group_id_str} عند محاولة الطرد. سيتم حذف عضويته من DB.")
                        db_manager.execute_query("DELETE FROM memberships WHERE user_id = ? AND group_id = ?", (user_id_to_kick, group_id_str))
                    elif any(s in error_lower for s in ["can't remove chat owner", "can't kick administrator", "rights to restrict/unrestrict"]):
                         logger.warning(f"لا يمكن طرد {user_id_to_kick} من {group_id_str} (مالك/مشرف أو البوت لا يملك صلاحية): {e_api_kick}")
                         bot.send_message(ADMIN_ID, f"⚠️ لم أتمكن من طرد {user_id_to_kick} من {group_id_str}. قد يكون مشرفًا أو البوت لا يملك صلاحية. الخطأ: {e_api_kick}")
                         db_manager.execute_query("UPDATE memberships SET notified = 1 WHERE user_id = ? AND group_id = ?", (user_id_to_kick, group_id_str))
                    else:
                        logger.error(f"خطأ API في طرد العضو {user_id_to_kick} من {group_id_str}: {str(e_api_kick)}", exc_info=True)
                except Exception as e_kick_generic:
                    logger.error(f"خطأ غير متوقع أثناء طرد {user_id_to_kick} من {group_id_str}: {str(e_kick_generic)}", exc_info=True)
            
            MembershipManager.notify_expired_memberships(bot, db_manager)
            
            logger.info("اكتمل فحص المهام الخلفية. الانتظار للدورة التالية (1 ساعة).")
            time.sleep(3600) 
            
        except Exception as e_bg_main:
            logger.error(f"خطأ فادح في حلقة المهام الخلفية: {str(e_bg_main)}", exc_info=True)
            try:
                bot.send_message(ADMIN_ID, f"🚨 خطأ فادح في مؤشر ترابط المهام الخلفية: {e_bg_main}\nسيتم محاولة إعادة التشغيل بعد 5 دقائق.")
            except: pass
            time.sleep(60 * 5) 


if __name__ == '__main__':
    logger.info("===================================")
    logger.info("   WelMemBot - Startup Initiated   ")
    logger.info("===================================")
    
    for path_to_check in [os.path.dirname(DB_PATH), os.path.dirname(LOG_FILE)]:
        if path_to_check and not os.path.exists(path_to_check):
            os.makedirs(path_to_check, exist_ok=True)
            logger.info(f"تم إنشاء المجلد: {path_to_check}")

    try:
        bg_thread = threading.Thread(target=scheduled_background_tasks, daemon=True)
        bg_thread.start()
        
        logger.info(f"⏳ البوت قيد التشغيل... (Admin: {ADMIN_ID}, Approved Groups: {APPROVED_GROUP_IDS})")

        try:
            bot.send_message(ADMIN_ID, "🚀 تم إعادة تشغيل البوت بنجاح وهو الآن متصل!")
        except Exception as startup_msg_err:
            logger.error(f"لم يتمكن من إرسال رسالة بدء التشغيل للأدمن: {startup_msg_err}")

        retry_delay = 5 
        max_retry_delay = 300 
        while True:
            try:
                bot.infinity_polling(logger_level=logging.WARNING, timeout=20, long_polling_timeout=30)
            except requests.exceptions.ConnectionError as e_conn_poll: 
                logger.error(f"خطأ اتصال بالشبكة (polling): {e_conn_poll}. إعادة المحاولة بعد {retry_delay} ثانية...")
            except telebot.apihelper.ApiTelegramException as e_api_poll:
                 logger.error(f"خطأ API من تيليجرام (polling): {e_api_poll}. إعادة المحاولة بعد {retry_delay} ثانية...")
                 if "Conflict" in str(e_api_poll): 
                     logger.critical("خطأ تضارب (409): نسخة أخرى من البوت تعمل بنفس التوكن. الإيقاف...")
                     bot.send_message(ADMIN_ID, "🚨 خطأ تضارب (409)! تم إيقاف البوت لأن نسخة أخرى تعمل بنفس التوكن.")
                     sys.exit(1) 
            except Exception as e_poll_main:
                logger.error(f"خطأ غير متوقع في حلقة التشغيل الرئيسية (polling): {str(e_poll_main)}", exc_info=True)
                try: bot.send_message(ADMIN_ID, f"🚨 خطأ فادح في البوت: {e_poll_main}\nأحاول إعادة الاتصال...")
                except: pass
            
            logger.info(f"إعادة محاولة الاتصال بعد {retry_delay} ثانية...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
    
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت يدويًا (KeyboardInterrupt).")
        try: bot.send_message(ADMIN_ID, "🛑 تم إيقاف البوت يدويًا.")
        except: pass
        sys.exit(0)
    except Exception as e_critical_startup: 
        logger.critical(f"❌ خطأ حرج جدًا منع تشغيل البوت: {str(e_critical_startup)}", exc_info=True)
        try: bot.send_message(ADMIN_ID, f"❌ فشل تشغيل البوت بسبب خطأ حرج: {e_critical_startup}")
        except: pass
        sys.exit(1)
