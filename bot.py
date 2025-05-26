# G1.0
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
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0' # استبدل هذا بالتوكن الخاص بك
ADMIN_ID = 764559466 # استبدل هذا بمعرف الأدمن الخاص بك
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db' # أو مسار مناسب لك
LOG_FILE = '/home/ec2-user/projects/WelMemBot/bot.log' # أو مسار مناسب لك

# قائمة المجموعات المعتمدة - هام: يجب أن يكون معرف المجموعة هنا كسلسلة نصية
APPROVED_GROUP_IDS = ['-1002329495586'] # استبدل هذا بمعرفات المجموعات المعتمدة

# إعداد التسجيل (Logging)
# تأكد من أن المسار الذي تكتب فيه ملف السجل موجود وقابل للكتابة
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'), # Ensure UTF-8 encoding for log file
        logging.StreamHandler(sys.stdout) # Also log to console
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
            # التأكد أن chat_id سلسلة نصية للمقارنة مع APPROVED_GROUP_IDS
            str_chat_id = str(chat_id)
            if str_chat_id not in APPROVED_GROUP_IDS:
                logger.warning(f"المجموعة {chat_id} غير معتمدة")
                return False, "هذه المجموعة غير معتمدة. تواصل مع المسؤول للاعتماد."
            
            # لا حاجة لجلب chat إذا لم نستخدم خصائصه مباشرة هنا
            # chat = bot_instance.get_chat(chat_id) 
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            
            # التحقق من الصلاحيات الأساسية
            # القيمة الافتراضية False إذا لم يكن الكائن يحتوي على الخاصية
            can_invite_users = getattr(bot_member, 'can_invite_users', False)
            can_restrict_members = getattr(bot_member, 'can_restrict_members', False)
            can_send_messages = getattr(bot_member, 'can_send_messages', False) # تم التعديل هنا

            required_permissions_status = {
                'can_invite_users': can_invite_users,
                'can_restrict_members': can_restrict_members,
                'can_send_messages': can_send_messages, # تم التعديل هنا
                'status': bot_member.status
            }
            
            logger.info(f"صلاحيات البوت في المجموعة {chat_id}: {required_permissions_status}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logger.warning(f"البوت ليس مشرفًا في المجموعة {chat_id}")
                return False, "البوت يجب أن يكون مشرفاً في المجموعة"
                
            missing_permissions = []
            if not can_invite_users:
                missing_permissions.append("إضافة أعضاء (دعوة مستخدمين عبر رابط)")
            if not can_restrict_members: # صلاحية الحظر مهمة لطرد الأعضاء منتهية عضويتهم
                missing_permissions.append("حظر أعضاء")
            if not can_send_messages: # تم التعديل هنا
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
            elif "user_not_participant" in error_msg or "member list is inaccessible" in error_msg: # قد تحدث إذا لم يكن البوت مشرفًا
                 return False, "البوت ليس لديه الصلاحية الكافية للوصول لمعلومات الأعضاء (قد لا يكون مشرفًا أو لا يملك صلاحية كافية)."
            logger.error(f"خطأ في API تيليجرام أثناء التحقق من الصلاحيات للمجموعة {chat_id}: {str(e)}")
            return False, f"خطأ في API تيليجرام: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع في التحقق من الصلاحيات للمجموعة {chat_id}: {str(e)}")
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
            except sqlite3.IntegrityError: # الكود موجود مسبقاً
                attempts += 1
                logger.warning(f"تضارب في الكود {code}، محاولة مرة أخرى.")
                continue
            except Exception as e:
                logger.error(f"خطأ عند إدخال الكود {code} في قاعدة البيانات: {e}")
                attempts +=1 # لمنع حلقة لا نهائية في حالة خطأ آخر
        if attempts >= max_attempts and len(codes) < count:
            logger.warning(f"تجاوز عدد المحاولات لتوليد الأكواد للمجموعة {group_id}. تم توليد {len(codes)} من {count} أكواد.")
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
            # expire_date timestamp needs to be integer
            expire_date = int(time.time()) + (24 * 60 * 60)  # 24 ساعة
            link = bot_instance.create_chat_invite_link(
                chat_id=group_id,
                name=f"Invite_{code[:10]}_{user_id}", # اسم الرابط يمكن أن يكون محدود الطول
                expire_date=expire_date,
                member_limit=1
            )
            logger.info(f"تم إنشاء رابط الدعوة بنجاح: {link.invite_link}")
            return link.invite_link, expire_date, None
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"خطأ في API تيليجرام أثناء إنشاء رابط الدعوة للمجموعة {group_id}: {str(e)}")
            error_msg = str(e).lower()
            if "need administrator rights" in error_msg or "not enough rights" in error_msg or "chat admin required" in error_msg:
                return None, None, "البوت يحتاج صلاحية 'دعوة مستخدمين عبر رابط' (can_invite_users) لإنشاء رابط دعوة. تأكد أنه مشرف بهذه الصلاحية."
            elif "privacy settings" in error_msg: # عادةً هذا الخطأ متعلق بالـ BotFather
                return None, None, "يرجى التحقق من إعدادات الخصوصية للبوت في @BotFather. قد تحتاج لتعطيل وضع الخصوصية باستخدام /setprivacy -> Disable."
            elif "chat not found" in error_msg:
                return None, None, "المجموعة غير موجودة أو المعرف غير صحيح."
            elif "bot is not a member" in error_msg:
                return None, None, "البوت ليس عضواً في المجموعة."
            return None, None, f"خطأ في API تيليجرام عند إنشاء الرابط: {str(e)}"
        except Exception as e:
            logger.error(f"خطأ غير متوقع أثناء إنشاء رابط الدعوة للمجموعة {group_id}: {str(e)}")
            return None, None, f"خطأ غير متوقع عند إنشاء الرابط: {str(e)}"
    
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
            logger.error(f"خطأ في تخزين رابط الدعوة {link_data[0]}: {str(e)}")
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
            # التحقق من الكود
            result = db_manager.execute_query(
                """SELECT group_id FROM codes 
                WHERE code = ? AND used = 0""",
                (code,),
                fetch=True
            )
            
            if not result:
                logger.warning(f"الكود {code} غير صالح أو مستخدم من قبل.")
                return False, "الكود غير صالح أو مستخدم من قبل."
            
            group_id = result[0]['group_id']
            if str(group_id) not in APPROVED_GROUP_IDS:
                logger.error(f"محاولة معالجة كود لمجموعة غير معتمدة: {group_id} (الكود: {code})")
                return False, "هذا الكود مخصص لمجموعة غير مدعومة حاليًا. تواصل مع المسؤول."
            
            logger.info(f"الكود {code} مرتبط بالمجموعة {group_id}")
            
            # التحقق إذا كان المستخدم عضواً بالفعل
            try:
                member = bot_instance.get_chat_member(group_id, user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    logger.info(f"المستخدم {user_id} بالفعل عضو في المجموعة {group_id}")
                    return False, "أنت بالفعل عضو في المجموعة!"
            except telebot.apihelper.ApiTelegramException as e:
                if "user not found" in str(e).lower() or "user_not_participant" in str(e).lower():
                    pass # المستخدم ليس عضواً، وهذا جيد
                else:
                    logger.error(f"خطأ في التحقق من حالة العضوية لـ {user_id} في {group_id}: {str(e)}")
                    return False, f"خطأ في التحقق من حالة عضويتك: {str(e)}"
            
            # التحقق من صلاحيات البوت في المجموعة المستهدفة
            success, perm_msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not success:
                logger.warning(f"فشل في التحقق من الصلاحيات للمجموعة {group_id} عند معالجة الكود {code}: {perm_msg}")
                # إبلاغ الأدمن بالمشكلة إذا كانت متعلقة بالصلاحيات
                bot_instance.send_message(ADMIN_ID, f"تنبيه: فشل التحقق من صلاحيات البوت في المجموعة {group_id} عند محاولة المستخدم {user_id} استخدام الكود {code}.\nالسبب: {perm_msg}\nيرجى مراجعة صلاحيات البوت في تلك المجموعة.")
                return False, f"حدث خطأ إداري يمنع إنشاء رابط الدعوة حاليًا. تم إبلاغ المسؤول. ({perm_msg})"
            
            invite_link, expire_time, error_msg = InviteManager.create_invite_link(
                bot_instance, group_id, user_id, code)
            
            if not invite_link:
                logger.error(f"فشل في إنشاء رابط الدعوة للمستخدم {user_id} للكود {code}: {error_msg}")
                # إبلاغ الأدمن بالمشكلة
                bot_instance.send_message(ADMIN_ID, f"تنبيه: فشل إنشاء رابط دعوة للمستخدم {user_id} (كود: {code}) للمجموعة {group_id}.\nالسبب: {error_msg}")
                return False, error_msg or "فشل في إنشاء رابط الدعوة. تم إبلاغ المسؤول."
            
            link_data = (
                invite_link, group_id, user_id, code,
                datetime.now().isoformat(), expire_time
            )
            if not InviteManager.store_invite_link(db_manager, link_data):
                logger.error(f"فشل في حفظ رابط الدعوة {invite_link} في قاعدة البيانات.")
                # لا يزال بإمكاننا إرسال الرابط للمستخدم، لكنه لن يُتتبع جيدًا
                # يمكن اختيار إرجاع خطأ هنا إذا كان التخزين حرجًا
            
            # تم استخدام الكود بنجاح (سيتم تحديث used في invite_links عند الانضمام الفعلي)
            # نحدث used في جدول codes هنا لأنه تم إنشاء رابط له
            db_manager.execute_query(
                """UPDATE codes SET user_id = ?, used = 1 
                WHERE code = ?""",
                (user_id, code)
            )
            logger.info(f"تم تحديث الكود {code} كمستخدم (تم إنشاء رابط) بواسطة {user_id}")
            
            return True, invite_link
            
        except Exception as e:
            logger.error(f"خطأ عام في معالجة الكود {code} للمستخدم {user_id}: {str(e)}")
            return False, f"حدث خطأ غير متوقع أثناء معالجة الكود. يرجى المحاولة مرة أخرى لاحقًا أو التواصل مع المسؤول."

    @staticmethod
    def send_welcome_message(bot_instance, db_manager, chat_id, user_id):
        """إرسال رسالة ترحيبية عند الانضمام"""
        try:
            str_chat_id = str(chat_id) # لضمان المقارنة الصحيحة
            if str_chat_id not in APPROVED_GROUP_IDS:
                logger.warning(f"محاولة إرسال رسالة ترحيب لمجموعة غير معتمدة: {chat_id}")
                return False
            
            user_info = bot_instance.get_chat(user_id) # نحصل على معلومات المستخدم من تيليجرام
            username = user_info.first_name or user_info.username or f"User_{user_id}"
            
            # جلب الرسالة الترحيبية من قاعدة البيانات
            welcome_result = db_manager.execute_query(
                "SELECT welcome_message FROM groups WHERE group_id = ?",
                (str_chat_id,), # استخدام str_chat_id
                fetch=True
            )
            
            default_welcome_msg = "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة وتجنب المغادرة قبل المدة المحددة لتجنب الإيقاف."
            welcome_msg_template = welcome_result[0]['welcome_message'] if welcome_result and welcome_result[0]['welcome_message'] else default_welcome_msg
            
            # استبدال {username} باسم المستخدم
            welcome_msg = welcome_msg_template.format(username=telebot.util.escape(username)) # Escape for Markdown safety
            
            # تسجيل العضوية أو تحديثها
            # التحقق إذا كان العضو موجودًا لتجنب تكرار الإدخال أو لتحديث تاريخ الانضمام إذا عاد
            existing_membership = db_manager.execute_query(
                "SELECT join_date FROM memberships WHERE user_id = ? AND group_id = ?",
                (user_id, str_chat_id),
                fetch=True
            )
            current_time_iso = datetime.now().isoformat()
            if not existing_membership:
                db_manager.execute_query(
                    """INSERT INTO memberships 
                    (user_id, group_id, join_date, notified) 
                    VALUES (?, ?, ?, 0)""", # notified = 0 عند الانضمام الجديد
                    (user_id, str_chat_id, current_time_iso)
                )
                logger.info(f"تم تسجيل عضوية جديدة للمستخدم {user_id} في المجموعة {chat_id}")
            else:
                 # إذا عاد المستخدم، نحدث تاريخ الانضمام ونعيد تعيين حالة الإشعار
                db_manager.execute_query(
                    """UPDATE memberships 
                    SET join_date = ?, notified = 0
                    WHERE user_id = ? AND group_id = ?""",
                    (current_time_iso, user_id, str_chat_id)
                )
                logger.info(f"تم تحديث تاريخ انضمام المستخدم {user_id} في المجموعة {chat_id}")

            try:
                bot_instance.send_message(chat_id, welcome_msg, parse_mode='Markdown')
                logger.info(f"تم إرسال رسالة الترحيب إلى المجموعة {chat_id} للمستخدم {user_id}")
            except telebot.apihelper.ApiTelegramException as e:
                if "can't send messages" in str(e).lower() or "bot is not a member" in str(e).lower() or "chat not found" in str(e).lower():
                    # إذا لم يتمكن البوت من إرسال الرسالة في المجموعة، يرسلها للأدمن
                    bot_instance.send_message(ADMIN_ID, 
                                            f"تنبيه: لم أتمكن من إرسال رسالة الترحيب في المجموعة {chat_id} (المستخدم: {username}, ID: {user_id}).\n"
                                            f"السبب المحتمل: {str(e)}\n"
                                            f"الرسالة كانت:\n{welcome_msg}")
                    logger.warning(f"لا يمكن إرسال رسائل في المجموعة {chat_id}. تم إرسال رسالة الترحيب إلى الأدمن. الخطأ: {e}")
                else:
                    raise e # أعد إثارة الخطأ إذا كان غير متوقع
            return True
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة الترحيب للمستخدم {user_id} في المجموعة {chat_id}: {str(e)}")
            # إرسال إشعار للأدمن في حالة فشل إرسال رسالة الترحيب لأي سبب آخر
            try:
                bot_instance.send_message(ADMIN_ID, f"فشل إرسال رسالة الترحيب للمستخدم {user_id} في المجموعة {chat_id}.\nالخطأ: {str(e)}")
            except Exception as admin_notify_err:
                logger.error(f"فشل إضافي في إبلاغ الأدمن بخطأ رسالة الترحيب: {admin_notify_err}")
            return False
    
    @staticmethod
    def notify_expired_memberships(bot_instance, db_manager):
        """إرسال إشعارات للأعضاء المنتهية عضويتهم (للأدمن)"""
        try:
            # الأعضاء الذين تجاوزوا 30 يومًا ولم يتم إشعار الأدمن بهم بعد
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            expired_members = db_manager.execute_query(
                """SELECT user_id, group_id, join_date 
                FROM memberships 
                WHERE join_date < ? AND notified = 0""", # فقط الذين لم يتم إشعارهم
                (thirty_days_ago,),
                fetch=True
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
                        f"الإجراء المقترح: التحقق من حالة العضو وطرده إذا لزم الأمر."
                    )
                    bot_instance.send_message(ADMIN_ID, admin_message, parse_mode='Markdown')
                    
                    # تحديث حالة الإشعار لتجنب إرساله مرة أخرى
                    db_manager.execute_query(
                        """UPDATE memberships 
                        SET notified = 1 
                        WHERE user_id = ? AND group_id = ?""",
                        (member['user_id'], member['group_id'])
                    )
                    logger.info(f"تم إرسال إشعار للأدمن عن انتهاء عضوية {member['user_id']} في المجموعة {member['group_id']}")
                    
                except telebot.apihelper.ApiTelegramException as e:
                    if "user not found" in str(e).lower():
                        logger.warning(f"المستخدم {member['user_id']} لم يعد موجودًا (أو خطأ في جلب معلوماته) عند إشعار انتهاء العضوية.")
                        # يمكن هنا تحديث notified=1 أيضًا أو حذف العضوية إذا كان المستخدم غير موجود فعلاً
                        db_manager.execute_query(
                            """UPDATE memberships SET notified = 1 WHERE user_id = ? AND group_id = ?""",
                            (member['user_id'], member['group_id'])
                        )
                    else:
                        logger.error(f"خطأ في API تيليجرام أثناء إرسال إشعار انتهاء العضوية للمسؤول عن {member['user_id']}: {str(e)}")
                except Exception as e_inner:
                    logger.error(f"خطأ غير متوقع أثناء معالجة إشعار انتهاء عضوية {member['user_id']}: {str(e_inner)}")
            
            return True
        except Exception as e:
            logger.error(f"خطأ عام في وظيفة إشعارات العضويات المنتهية: {str(e)}")
            return False

# تهيئة مدير قاعدة البيانات
db_manager = DatabaseManager(DB_PATH)

# ===== معالجات الأوامر =====

@bot.message_handler(commands=['start', 'help'])
def start(message):
    """معالجة أمر /start"""
    user_id = message.from_user.id
    logger.info(f"أمر /start أو /help من المستخدم {user_id} ({message.from_user.username})")
    
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1) # لتظهر الأزرار تحت بعضها
        markup.add(InlineKeyboardButton("⚙️ إنشاء أكواد جديدة", callback_data="generate_codes"))
        markup.add(InlineKeyboardButton("📊 عرض الأكواد والروابط", callback_data="show_codes_links"))
        markup.add(InlineKeyboardButton("💬 تعديل رسالة الترحيب", callback_data="set_welcome_cmd"))
        
        bot.reply_to(message, "أهلاً بك أيها الأدمن! 👋\nاختر الإجراء المطلوب من القائمة:", reply_markup=markup)
    else:
        bot.reply_to(message, 
                     "مرحبًا بك! 👋\n"
                     "إذا كان لديك كود للانضمام إلى إحدى المجموعات، يرجى إرساله الآن.")
        bot.register_next_step_handler(message, check_code_from_user_message) # تغيير اسم الدالة

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """معالجة الأزرار"""
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ هذا الأمر مخصص للأدمن فقط!", show_alert=True)
        return

    try:
        bot.answer_callback_query(call.id) # تأكيد استلام الضغطة أولاً
        if call.data == "generate_codes":
            bot.send_message(call.message.chat.id, "يرجى إدخال معرف المجموعة (Group ID) التي تريد إنشاء أكواد لها:")
            bot.register_next_step_handler(call.message, get_group_id_for_code_generation)
        elif call.data == "show_codes_links":
            show_codes_links_options(call.message) # تغيير اسم الدالة
        elif call.data.startswith("group_links_"):
            group_id = call.data.split("_")[2]
            show_specific_group_links(call.message, group_id) # تغيير اسم الدالة
        elif call.data == "set_welcome_cmd":
            bot.send_message(call.message.chat.id, 
                             "لتعديل رسالة الترحيب، أرسل الأمر التالي:\n"
                             "`/set_welcome GROUP_ID رسالتك هنا`\n\n"
                             "مثال:\n"
                             "`/set_welcome -1001234567890 🎉 مرحباً {username}! نورت المجموعة.`\n\n"
                             "تذكر أن `{username}` سيتم استبداله باسم العضو الجديد.\n"
                             "إذا كنت داخل المجموعة وتريد تعيين رسالتها، يمكنك استخدام:\n"
                             "`/set_welcome رسالتك هنا` (سيتم تحديد ID المجموعة تلقائياً).")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار (callback_query): {str(e)}")
        try:
            bot.answer_callback_query(call.id, "حدث خطأ ما، يرجى المحاولة لاحقًا.", show_alert=True)
        except: # إذا فشل الرد على الكول باك نفسه
            pass

# تم تغيير اسم الدالة لتفادي التعارض مع check_code (المستخدم من قبل المستخدم العادي)
def check_code_from_user_message(message):
    """التحقق من الكود المدخل من المستخدم العادي"""
    code_text = message.text.strip().upper()
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "عضو جديد"
    username_mention = f"@{message.from_user.username}" if message.from_user.username else first_name

    logger.info(f"الكود المدخل من المستخدم {user_id} ({username_mention}): {code_text}")
    
    success, result_or_msg = MembershipManager.process_code(bot, db_manager, user_id, code_text)
    
    if success: # result_or_msg هو رابط الدعوة
        bot.reply_to(message, 
                     f"مرحبًا {telebot.util.escape(first_name)}!\n\n"
                     f"✅ تم التحقق من الكود بنجاح.\n"
                     f"إليك رابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة ولمستخدم واحد فقط):\n"
                     f"{result_or_msg}\n\n"
                     "⚠️ عضويتك في المجموعة ستكون لمدة شهر واحد، وبعدها قد يتم إزالتك تلقائيًا.\n"
                     "يرجى الالتزام بقوانين المجموعة.", 
                     parse_mode='Markdown')
        logger.info(f"تم إرسال رابط الدعوة {result_or_msg} للمستخدم {user_id} ({username_mention}) للكود {code_text}")
    else: # result_or_msg هو رسالة الخطأ
        bot.reply_to(message, 
                     f"عذرًا {telebot.util.escape(first_name)}، حدث خطأ:\n\n"
                     f"🚫 {telebot.util.escape(result_or_msg)}\n\n"
                     "يرجى التأكد من صحة الكود والمحاولة مرة أخرى، أو التواصل مع المسؤول إذا استمرت المشكلة.")
        logger.warning(f"فشل في معالجة الكود {code_text} للمستخدم {user_id} ({username_mention}): {result_or_msg}")


def get_group_id_for_code_generation(message):
    """الحصول على معرف المجموعة من الأدمن لإنشاء الأكواد"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    group_id_input = message.text.strip()
    logger.info(f"الأدمن أدخل معرف المجموعة لإنشاء الأكواد: {group_id_input}")
    
    try:
        # التحقق من أن معرف المجموعة يبدأ بـ -100 (للمجموعات الخارقة) أو - (للمجموعات العادية)
        # هذا التحقق قد لا يكون دقيقًا 100% لكل أنواع المجموعات، لكنه شائع
        if not (group_id_input.startswith('-100') or (group_id_input.startswith('-') and group_id_input[1:].isdigit())):
            bot.reply_to(message, "⚠️ معرف المجموعة غير صالح! يجب أن يكون رقمًا سالبًا (مثال: -1001234567890 أو -123456789).")
            return
        
        # التحقق من أن المجموعة معتمدة
        if group_id_input not in APPROVED_GROUP_IDS:
            bot.reply_to(message, f"⚠️ المجموعة ذات المعرف {group_id_input} غير موجودة في قائمة المجموعات المعتمدة.\n"
                                  f"يرجى إضافتها إلى `APPROVED_GROUP_IDS` في الكود أولاً أو التأكد من صحة المعرف.")
            return
        
        # محاولة جلب معلومات المجموعة للتحقق من وجودها وصلاحيات البوت
        chat_info = bot.get_chat(group_id_input) # سيثير استثناء إذا لم يتم العثور على المجموعة
        
        success, perm_msg = BotPermissions.check_bot_permissions(bot, group_id_input)
        if not success:
            bot.reply_to(message, f"❌ خطأ في صلاحيات البوت للمجموعة {chat_info.title} ({group_id_input}):\n{perm_msg}\n\n"
                                  "يرجى منح البوت الصلاحيات المطلوبة في تلك المجموعة ثم المحاولة مرة أخرى.")
            return
        
        # إذا لم تكن المجموعة موجودة في جدول groups، قم بإضافتها برسالة ترحيب افتراضية
        group_exists_in_db = db_manager.execute_query("SELECT 1 FROM groups WHERE group_id = ?", (group_id_input,), fetch=True)
        if not group_exists_in_db:
            default_welcome = "🎉 مرحبًا بك، {username}!\n📅 عضويتك ستنتهي بعد شهر تلقائيًا.\n📜 يرجى الالتزام بقواعد المجموعة."
            db_manager.execute_query(
                "INSERT OR IGNORE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
                (group_id_input, default_welcome, 1 if chat_info.type in ['group', 'supergroup'] else 0)
            )
            logger.info(f"تم إضافة المجموعة {group_id_input} إلى جدول groups تلقائيًا.")

        bot.reply_to(message, f"✅ تم تحديد المجموعة بنجاح: {chat_info.title} (ID: {group_id_input}).\n"
                              "الآن، أدخل عدد الأكواد التي ترغب في إنشائها لهذه المجموعة (مثال: 10):")
        bot.register_next_step_handler(message, lambda m: generate_new_codes(m, group_id_input)) # تغيير اسم الدالة
        
    except telebot.apihelper.ApiTelegramException as e:
        if "chat not found" in str(e).lower():
            bot.reply_to(message, f"❌ لم أتمكن من العثور على مجموعة بالمعرف {group_id_input}. يرجى التأكد من صحة المعرف وأن البوت عضو فيها.")
        else:
            bot.reply_to(message, f"❌ خطأ في API تيليجرام عند محاولة الوصول للمجموعة {group_id_input}: {str(e)}")
        logger.error(f"خطأ API في get_group_id_for_code_generation للمجموعة {group_id_input}: {str(e)}")
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع: {str(e)}")
        logger.error(f"خطأ عام في get_group_id_for_code_generation للمجموعة {group_id_input}: {str(e)}")

def generate_new_codes(message, group_id): # تغيير اسم الدالة
    """توليد الأكواد للمجموعة المحددة من قبل الأدمن"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    if str(group_id) not in APPROVED_GROUP_IDS: # إعادة التحقق
        bot.reply_to(message, f"⚠️ المجموعة {group_id} غير معتمدة. هذا غير متوقع. يرجى التواصل مع المطور.")
        logger.error(f"محاولة توليد أكواد لمجموعة {group_id} غير معتمدة داخل generate_new_codes.")
        return
    
    try:
        num_codes_str = message.text.strip()
        if not num_codes_str.isdigit() or int(num_codes_str) <= 0:
            bot.reply_to(message, "⚠️ يرجى إدخال عدد صحيح موجب للأكواد (مثال: 5).")
            # إعادة تسجيل الخطوة لطلب عدد الأكواد مرة أخرى
            bot.register_next_step_handler(message, lambda m: generate_new_codes(m, group_id))
            return
        
        num_codes = int(num_codes_str)
        if num_codes > 100: # حد أقصى لعدد الأكواد في المرة الواحدة
             bot.reply_to(message, "⚠️ لا يمكن إنشاء أكثر من 100 كود في المرة الواحدة. يرجى إدخال عدد أقل.")
             bot.register_next_step_handler(message, lambda m: generate_new_codes(m, group_id))
             return

        generated_codes = CodeGenerator.generate_multiple_codes(db_manager, group_id, num_codes)
        
        if not generated_codes:
            bot.reply_to(message, "⚠️ حدث خطأ أثناء توليد الأكواد أو لم يتم توليد أي أكواد (قد تكون هناك مشكلة في قاعدة البيانات أو تضارب كبير في الأكواد). يرجى المحاولة مرة أخرى أو مراجعة السجلات.")
            return
            
        # تقسيم الأكواد إلى مجموعات إذا كانت كثيرة لتجنب تجاوز حد طول الرسالة
        codes_str_list = [f"`{code}`" for code in generated_codes]
        
        reply_message = f"✅ تم بنجاح توليد {len(generated_codes)} كود/أكواد جديدة للمجموعة `{group_id}`:\n\n"
        
        # إرسال الأكواد في رسائل متعددة إذا لزم الأمر
        current_batch = ""
        for i, code_md in enumerate(codes_str_list):
            if len(reply_message + current_batch + code_md + "\n") > 4000: # Telegram message length limit is 4096
                bot.send_message(message.chat.id, reply_message + current_batch, parse_mode='Markdown')
                current_batch = "" # ابدأ دفعة جديدة
            current_batch += code_md + "\n"
            if (i + 1) % 20 == 0 and i < len(codes_str_list) -1 : # فاصل كل 20 كود للوضوح
                current_batch += "\n"


        if current_batch: # إرسال ما تبقى
             bot.send_message(message.chat.id, reply_message + current_batch, parse_mode='Markdown')
        
        bot.send_message(message.chat.id, "يمكنك نسخ الأكواد من الأعلى ومشاركتها مع الأعضاء للانضمام إلى المجموعة.")
        logger.info(f"الأدمن {message.from_user.id} قام بتوليد {len(generated_codes)} أكواد للمجموعة {group_id}")
        
    except ValueError: # في حالة فشل تحويل num_codes إلى int (تم التعامل معه أعلاه بـ isdigit)
        bot.reply_to(message, "⚠️ يرجى إدخال رقم صحيح لعدد الأكواد!")
        bot.register_next_step_handler(message, lambda m: generate_new_codes(m, group_id))
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع أثناء توليد الأكواد: {str(e)}")
        logger.error(f"خطأ في generate_new_codes للمجموعة {group_id}: {str(e)}")

def show_codes_links_options(message): # تغيير اسم الدالة
    """عرض خيارات المجموعات لعرض الأكواد والروابط الخاصة بها"""
    if message.from_user.id != ADMIN_ID: # حماية إضافية
        bot.reply_to(message, "🚫 هذا الإجراء مخصص للأدمن فقط.")
        return
        
    try:
        # جلب المجموعات المعتمدة فقط التي لها وجود في جدول groups
        # ونحاول جلب اسم المجموعة من تيليجرام إذا أمكن
        groups_from_db = db_manager.execute_query(
            "SELECT group_id FROM groups WHERE group_id IN ({seq})".format(
                seq=','.join(['?']*len(APPROVED_GROUP_IDS))),
            tuple(APPROVED_GROUP_IDS),
            fetch=True
        )
        
        if not groups_from_db:
            bot.reply_to(message, "ℹ️ لا توجد مجموعات معتمدة مسجلة في قاعدة البيانات حاليًا أو لم يتم إنشاء أكواد لأي منها بعد.")
            return
            
        markup = InlineKeyboardMarkup(row_width=1)
        found_groups = False
        for group_row in groups_from_db:
            group_id_val = group_row['group_id']
            group_title = group_id_val # اسم افتراضي
            try:
                chat_info = bot.get_chat(group_id_val)
                group_title = chat_info.title or group_id_val
            except Exception as e:
                logger.warning(f"لم يتمكن من جلب اسم المجموعة {group_id_val}: {e}")

            markup.add(InlineKeyboardButton(
                f"المجموعة: {group_title} ({group_id_val})", 
                callback_data=f"group_links_{group_id_val}")
            )
            found_groups = True
        
        if not found_groups: # إذا لم يتم العثور على أي مجموعة يمكن عرضها
             bot.reply_to(message, "ℹ️ لم يتم العثور على مجموعات معتمدة لديها أكواد أو روابط لعرضها حاليًا.")
             return

        bot.reply_to(message, "اختر المجموعة لعرض الأكواد والروابط الخاصة بها:", reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء محاولة عرض خيارات المجموعات: {str(e)}")
        logger.error(f"خطأ في show_codes_links_options: {str(e)}")

def show_specific_group_links(message, group_id): # تغيير اسم الدالة
    """عرض روابط وأكواد مجموعة محددة للأدمن"""
    if message.from_user.id != ADMIN_ID: # حماية إضافية
        bot.edit_message_text("🚫 هذا الإجراء مخصص للأدمن فقط.", chat_id=message.chat.id, message_id=message.message_id)
        return

    if str(group_id) not in APPROVED_GROUP_IDS:
        bot.edit_message_text(f"⚠️ المجموعة {group_id} غير معتمدة أو غير موجودة في القائمة.", chat_id=message.chat.id, message_id=message.message_id)
        return
    
    try:
        # جلب اسم المجموعة
        group_title = group_id
        try:
            chat_info = bot.get_chat(group_id)
            group_title = chat_info.title or group_id
        except Exception:
            pass

        # جلب الأكواد المستخدمة
        used_codes_q = db_manager.execute_query(
            """SELECT code, user_id, strftime('%Y-%m-%d %H:%M', created_at) as created_at_fmt 
            FROM codes 
            WHERE group_id = ? AND used = 1
            ORDER BY created_at DESC LIMIT 20""", # حد لعدد النتائج
            (group_id,),
            fetch=True
        )
        
        # جلب الأكواد غير المستخدمة
        unused_codes_q = db_manager.execute_query(
            """SELECT code, strftime('%Y-%m-%d %H:%M', created_at) as created_at_fmt
            FROM codes 
            WHERE group_id = ? AND used = 0
            ORDER BY created_at DESC LIMIT 20""", # حد لعدد النتائج
            (group_id,),
            fetch=True
        )
        
        # جلب روابط الدعوة (المستخدمة وغير المستخدمة)
        invite_links_q = InviteManager.get_invite_links(db_manager, group_id) # هذا يجلب كل الروابط للمجموعة
        
        response_msg = f"📊 *معلومات الأكواد والروابط للمجموعة: {telebot.util.escape(group_title)} ({group_id})*\n\n"
        
        response_msg += "未使用のコード (أحدث 20):\n" # الأكواد غير المستخدمة
        if unused_codes_q:
            response_msg += "\n".join([f"- `{code['code']}` (作成日時: {code['created_at_fmt']})" for code in unused_codes_q])
        else:
            response_msg += "利用可能な未使用のコードはありません。"
        response_msg += "\n\n"
        
        response_msg += "使用済みのコード (أحدث 20):\n" # الأكواد المستخدمة
        if used_codes_q:
            response_msg += "\n".join([f"- `{code['code']}` (使用者ID: `{code['user_id'] or 'غير معروف'}` | 作成日時: {code['created_at_fmt']})" for code in used_codes_q])
        else:
            response_msg += "使用済みのコードはありません。"
        response_msg += "\n\n"
        
        response_msg += "招待リンク (أحدث 10 روابط، مع حالتها):\n" # روابط الدعوة
        if invite_links_q:
            # فرز الروابط وعرض أحدث 10
            sorted_links = sorted(invite_links_q, key=lambda x: x['created_time'], reverse=True)[:10]
            for link_info in sorted_links:
                is_link_used = link_info['used'] == 1
                # expire_time هو timestamp
                is_link_expired = datetime.now().timestamp() >= link_info['expire_time']
                
                status_parts = []
                if is_link_used:
                    status_parts.append("🔴 使用済み")
                if is_link_expired:
                    status_parts.append("⚠️ 期限切れ")
                if not is_link_used and not is_link_expired:
                    status_parts.append("🟢 有効")

                status_str = ", ".join(status_parts)
                
                try:
                    expire_dt = datetime.fromtimestamp(link_info['expire_time']).strftime('%Y-%m-%d %H:%M')
                    created_dt = datetime.fromisoformat(link_info['created_time']).strftime('%Y-%m-%d %H:%M')
                except:
                    expire_dt = "غير معروف"
                    created_dt = "غير معروف"

                response_msg += (f"— リンク: `{link_info['link']}`\n"
                                 f"  コード: `{link_info['code']}` | ユーザーID: `{link_info['user_id'] or 'N/A'}`\n"
                                 f"  状態: {status_str}\n"
                                 f"  作成日時: {created_dt} | 有効期限: {expire_dt}\n\n")
        else:
            response_msg += "このグループの招待リンクはありません。"
        
        # استخدام edit_message_text لتحديث الرسالة الحالية بدلاً من إرسال واحدة جديدة
        # يجب التأكد من أن طول الرسالة لا يتجاوز الحد الأقصى
        if len(response_msg) > 4096:
            response_msg = response_msg[:4090] + "\n(... المزيد من البيانات، تم الاقتصاص)"

        bot.edit_message_text(response_msg, chat_id=message.chat.id, message_id=message.message_id, parse_mode='Markdown')

    except Exception as e:
        error_text = f"❌ حدث خطأ أثناء عرض معلومات المجموعة {group_id}: {str(e)}"
        logger.error(f"خطأ في show_specific_group_links للمجموعة {group_id}: {str(e)}")
        try:
            bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=message.message_id)
        except: # إذا فشل تعديل الرسالة نفسها
             bot.send_message(message.chat.id, error_text)


@bot.message_handler(commands=['set_welcome'])
def set_welcome_message_command(message): # تغيير اسم الدالة
    """تعيين رسالة ترحيب مخصصة للمجموعة (أمر للأدمن)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 غير مصرح لك باستخدام هذا الأمر!")
        return
    
    args = message.text.split(maxsplit=1) # يفصل الأمر عن باقي النص
    
    # الحالة 1: الأمر داخل مجموعة (/set_welcome نص الرسالة)
    if message.chat.type in ['group', 'supergroup']:
        target_group_id = str(message.chat.id)
        if len(args) < 2 or not args[1].strip():
            bot.reply_to(message, 
                         "⚠️ يرجى تحديد نص رسالة الترحيب بعد الأمر.\n"
                         "مثال داخل المجموعة: `/set_welcome أهلاً بك {username}!`\n"
                         "تذكر: `{username}` سيتم استبداله باسم العضو.")
            return
        welcome_text = args[1].strip()
    # الحالة 2: الأمر في الخاص مع البوت (/set_welcome group_id نص الرسالة)
    elif message.chat.type == 'private':
        args_private = message.text.split(maxsplit=2) # /set_welcome group_id text
        if len(args_private) < 3 or not args_private[1].strip() or not args_private[2].strip():
            bot.reply_to(message, 
                         "⚠️ للاستخدام في الخاص، يرجى تحديد معرف المجموعة ثم رسالة الترحيب.\n"
                         "مثال: `/set_welcome -1001234567890 مرحباً بك يا {username}!`\n"
                         "تذكر: `{username}` سيتم استبداله باسم العضو.")
            return
        target_group_id = args_private[1].strip()
        welcome_text = args_private[2].strip()
    else: # أنواع محادثات أخرى غير مدعومة
        bot.reply_to(message, "لا يمكن استخدام هذا الأمر في هذا النوع من المحادثات.")
        return

    # التحقق من أن المجموعة معتمدة
    if target_group_id not in APPROVED_GROUP_IDS:
        bot.reply_to(message, f"⚠️ المجموعة ذات المعرف {target_group_id} غير موجودة في قائمة المجموعات المعتمدة.\n"
                              "يرجى إضافتها إلى `APPROVED_GROUP_IDS` في الكود أولاً.")
        return
    
    # التحقق من صحة معرف المجموعة (بسيط)
    if not (target_group_id.startswith('-') and target_group_id[1:].isdigit()):
        bot.reply_to(message, "⚠️ معرف المجموعة الذي أدخلته غير صالح. يجب أن يكون رقمًا سالبًا.")
        return

    try:
        # محاولة جلب معلومات المجموعة للتأكد من وجودها وأن البوت عضو فيها ومشرف
        # هذا أيضًا يضمن أن البوت يمكنه إرسال رسائل هناك
        perm_success, perm_msg = BotPermissions.check_bot_permissions(bot, target_group_id)
        if not perm_success:
             bot.reply_to(message, f"❌ لا يمكن تعيين رسالة الترحيب للمجموعة {target_group_id}.\nالسبب: {perm_msg}\nيرجى التأكد من أن البوت عضو ومشرف بالصلاحيات اللازمة في تلك المجموعة.")
             return

        # تحديث أو إدراج رسالة الترحيب في قاعدة البيانات
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, COALESCE((SELECT is_private FROM groups WHERE group_id = ?), 1))",
            (target_group_id, welcome_text, target_group_id) # COALESCE للحفاظ على is_private إذا كانت موجودة
        )
        bot.reply_to(message, f"✅ تم تحديث رسالة الترحيب للمجموعة `{target_group_id}` بنجاح إلى:\n\n`{telebot.util.escape(welcome_text)}`", parse_mode='Markdown')
        logger.info(f"الأدمن {message.from_user.id} قام بتحديث رسالة الترحيب للمجموعة {target_group_id} إلى: {welcome_text}")
    except telebot.apihelper.ApiTelegramException as e:
         bot.reply_to(message, f"❌ خطأ من تيليجرام عند محاولة الوصول للمجموعة {target_group_id}: {e}\nتأكد أن المعرف صحيح وأن البوت عضو ومشرف في المجموعة.")
         logger.error(f"خطأ API في set_welcome_message_command للمجموعة {target_group_id}: {e}")
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع: {str(e)}")
        logger.error(f"خطأ عام في set_welcome_message_command للمجموعة {target_group_id}: {str(e)}")


# معالج للعضوية الجديدة (عندما ينضم عضو)
@bot.chat_member_handler()
def handle_chat_member_update(update: telebot.types.ChatMemberUpdated):
    """معالجة تحديثات حالة عضو في المجموعة (انضمام، مغادرة، إلخ)"""
    try:
        chat_id_str = str(update.chat.id)
        if chat_id_str not in APPROVED_GROUP_IDS:
            # تجاهل المجموعات غير المعتمدة بصمت لتجنب إغراق السجلات
            # logger.debug(f"تحديث عضوية في مجموعة غير معتمدة: {chat_id_str}")
            return

        logger.info(f"تحديث حالة عضوية في المجموعة {chat_id_str}: "
                    f"المستخدم {update.new_chat_member.user.id} ({update.new_chat_member.user.first_name}), "
                    f"الحالة القديمة: {update.old_chat_member.status}, "
                    f"الحالة الجديدة: {update.new_chat_member.status}")

        # إذا انضم عضو جديد إلى المجموعة وكان مدعوًا عبر رابط دعوة أنشأه البوت
        if update.new_chat_member.status == 'member' and \
           (update.old_chat_member.status == 'left' or update.old_chat_member.status == 'kicked' or not update.old_chat_member.status): # أو إذا لم يكن عضواً من قبل
            
            user_id = update.new_chat_member.user.id
            invite_link_obj = getattr(update, 'invite_link', None)

            if invite_link_obj and invite_link_obj.creator.id == bot.get_me().id:
                logger.info(f"العضو {user_id} انضم إلى المجموعة {chat_id_str} عبر رابط دعوة أنشأه البوت: {invite_link_obj.invite_link}")
                # تحديث حالة استخدام رابط الدعوة في قاعدة البيانات
                db_manager.execute_query(
                    "UPDATE invite_links SET used = 1 WHERE link = ?",
                    (invite_link_obj.invite_link,)
                )
                # الكود المرتبط بهذا الرابط يجب أن يكون قد تم تحديثه كـ used=1 عند إنشاء الرابط
                # ولكن يمكن إضافة تحقق إضافي أو تحديث هنا إذا لزم الأمر.
                # result = db_manager.execute_query("SELECT code FROM invite_links WHERE link = ?", (invite_link_obj.invite_link,), fetch=True)
                # if result and result[0]['code']:
                #     db_manager.execute_query("UPDATE codes SET used = 1, user_id = ? WHERE code = ?", (user_id, result[0]['code']))

                logger.info(f"تم تحديث رابط الدعوة {invite_link_obj.invite_link} كـ 'مستخدم' لانضمام العضو {user_id}.")
            else:
                # انضم العضو بطريقة أخرى (ليس عبر رابط من البوت أو رابط غير معروف)
                logger.info(f"العضو {user_id} انضم إلى المجموعة {chat_id_str} (قد لا يكون عبر رابط البوت أو الرابط غير متتبع).")


            # إرسال الرسالة الترحيبية في كل الأحوال عند انضمام عضو جديد للمجموعة المعتمدة
            # (طالما أن البوت لديه صلاحية إرسال الرسائل)
            MembershipManager.send_welcome_message(bot, db_manager, update.chat.id, user_id)
        
        # التعامل مع مغادرة العضو
        elif update.new_chat_member.status == 'left' or update.new_chat_member.status == 'kicked':
            user_id = update.new_chat_member.user.id
            logger.info(f"العضو {user_id} غادر المجموعة {chat_id_str} أو تم طرده.")
            # يمكن هنا حذف العضوية من جدول memberships إذا أردت، أو تركها للتتبع
            # db_manager.execute_query("DELETE FROM memberships WHERE user_id = ? AND group_id = ?", (user_id, chat_id_str))
            # logger.info(f"تم حذف بيانات عضوية المستخدم {user_id} من المجموعة {chat_id_str} بعد المغادرة/الطرد.")

    except Exception as e:
        logger.error(f"خطأ في معالجة تحديث حالة العضو (handle_chat_member_update): {str(e)}", exc_info=True)


# ===== الوظائف الخلفية =====

def background_tasks_scheduler():
    """جدولة وتنفيذ المهام الخلفية بشكل دوري"""
    logger.info("بدء مؤشر ترابط المهام الخلفية...")
    while True:
        try:
            logger.info("التحقق من الروابط المنتهية الصلاحية...")
            now_timestamp = int(time.time())
            # تحديد الروابط المنتهية الصلاحية والتي لم يتم تعليمها كمستخدمة بعد
            expired_links_to_update = db_manager.execute_query(
                "SELECT link FROM invite_links WHERE expire_time < ? AND used = 0",
                (now_timestamp,),
                fetch=True
            )
            for link_row in expired_links_to_update:
                db_manager.execute_query(
                    "UPDATE invite_links SET used = 1 WHERE link = ?", # تعليمها كـ "مستخدمة" بمعنى أنها لم تعد صالحة
                    (link_row['link'],)
                )
                logger.info(f"تم تعليم رابط الدعوة المنتهي الصلاحية {link_row['link']} كـ 'مستخدم' (منتهي).")
            
            logger.info("التحقق من العضويات المنتهية الصلاحية (للطرد والإشعار)...")
            thirty_days_ago_iso = (datetime.now() - timedelta(days=30)).isoformat()
            
            # جلب الأعضاء الذين يجب طردهم (تجاوزوا 30 يومًا)
            members_to_kick = db_manager.execute_query(
                """SELECT user_id, group_id 
                FROM memberships 
                WHERE join_date < ?""", # كل من تجاوز 30 يوم
                (thirty_days_ago_iso,),
                fetch=True
            )
            
            for member in members_to_kick:
                group_id_str = str(member['group_id'])
                if group_id_str not in APPROVED_GROUP_IDS:
                    logger.warning(f"تجاهل طرد عضو من مجموعة غير معتمدة: {group_id_str}, المستخدم: {member['user_id']}")
                    continue
                
                user_id_to_kick = member['user_id']
                
                try:
                    # التأكد من أن البوت لا يزال لديه صلاحية الحظر
                    perm_success, perm_msg = BotPermissions.check_bot_permissions(bot, group_id_str)
                    if not perm_success or "حظر أعضاء" in perm_msg: # إذا كانت صلاحية الحظر مفقودة
                        logger.warning(f"لا يمكن طرد العضو {user_id_to_kick} من {group_id_str} بسبب نقص صلاحية 'حظر أعضاء': {perm_msg}")
                        bot.send_message(ADMIN_ID, f"⚠️ لا يمكن طرد العضو {user_id_to_kick} من المجموعة {group_id_str} بسبب نقص صلاحية 'حظر أعضاء'. يرجى مراجعة صلاحيات البوت.")
                        continue # انتقل للعضو التالي

                    bot.kick_chat_member(group_id_str, user_id_to_kick)
                    # يمكنك اختيار إلغاء حظره فورًا إذا كنت تريد فقط إزالته وليس حظره بشكل دائم
                    # bot.unban_chat_member(group_id_str, user_id_to_kick) 
                    logger.info(f"تم طرد العضو {user_id_to_kick} من المجموعة {group_id_str} لانتهاء عضويته.")
                    
                    # حذف العضوية من قاعدة البيانات بعد الطرد الناجح
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (user_id_to_kick, group_id_str)
                    )
                    logger.info(f"تم حذف عضوية {user_id_to_kick} من {group_id_str} بعد الطرد.")

                    # إرسال رسالة للأدمن عن الطرد
                    try:
                        user_info = bot.get_chat(user_id_to_kick)
                        kicked_username = user_info.first_name or user_info.username or f"User_{user_id_to_kick}"
                        bot.send_message(ADMIN_ID, 
                                         f"🗑️ تم طرد العضو {telebot.util.escape(kicked_username)} (ID: `{user_id_to_kick}`) "
                                         f"من المجموعة `{group_id_str}` لانتهاء فترة عضويته.",
                                         parse_mode='Markdown')
                    except Exception as notify_err:
                         logger.error(f"فشل إبلاغ الأدمن بطرد {user_id_to_kick}: {notify_err}")

                except telebot.apihelper.ApiTelegramException as e:
                    error_lower = str(e).lower()
                    if "user not found" in error_lower or "user_not_participant" in error_lower:
                        logger.warning(f"العضو {user_id_to_kick} غير موجود بالفعل في المجموعة {group_id_str} عند محاولة الطرد. سيتم حذف عضويته من قاعدة البيانات.")
                        db_manager.execute_query(
                            "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                            (user_id_to_kick, group_id_str)
                        )
                    elif "can't remove chat owner" in error_lower or "can't kick administrator" in error_lower or "rights to restrict/unrestrict" in error_lower:
                         logger.warning(f"لا يمكن طرد العضو {user_id_to_kick} من المجموعة {group_id_str} (قد يكون مالك/مشرف أو البوت لا يملك صلاحية كافية): {e}")
                         # يمكن إرسال إشعار للأدمن هنا
                         bot.send_message(ADMIN_ID, f"⚠️ لم أتمكن من طرد العضو {user_id_to_kick} من المجموعة {group_id_str}. قد يكون مالك/مشرف أو أن البوت لا يملك صلاحية الحظر. الخطأ: {e}")
                         # نحدث notified=1 لمنع محاولات الطرد المتكررة لهذا المستخدم إذا كان مشرفًا مثلاً
                         db_manager.execute_query("UPDATE memberships SET notified = 1 WHERE user_id = ? AND group_id = ?", (user_id_to_kick, group_id_str))
                    else:
                        logger.error(f"خطأ API في طرد العضو {user_id_to_kick} من {group_id_str}: {str(e)}")
                except Exception as e_kick:
                    logger.error(f"خطأ غير متوقع أثناء طرد العضو {user_id_to_kick} من {group_id_str}: {str(e_kick)}")
            
            # إرسال إشعارات للأدمن عن الأعضاء الذين انتهت عضويتهم ولم يتم إشعارهم بعد
            # (هذه الدالة الآن سترسل فقط إذا كان notified=0)
            MembershipManager.notify_expired_memberships(bot, db_manager)
            
            logger.info("اكتمل فحص المهام الخلفية. الانتظار للدورة التالية...")
            time.sleep(3600) # الانتظار لمدة ساعة (3600 ثانية)
            
        except Exception as e:
            logger.error(f"خطأ فادح في حلقة المهام الخلفية الرئيسية: {str(e)}", exc_info=True)
            bot.send_message(ADMIN_ID, f"🚨 خطأ فادح في مؤشر ترابط المهام الخلفية: {e}\nسيتم محاولة إعادة التشغيل بعد فترة قصيرة.")
            time.sleep(60 * 5) # انتظار 5 دقائق قبل المحاولة مرة أخرى في حالة الخطأ الفادح


# بدء البوت
if __name__ == '__main__':
    logger.info("===================================")
    logger.info("      بدء تشغيل بوت إدارة العضويات      ")
    logger.info("===================================")
    
    # التأكد من أن مجلدات قاعدة البيانات والسجلات موجودة
    # (تمت إضافتها داخل مُنشِئات الفئات المعنية أيضًا)
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(os.path.dirname(LOG_FILE)):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    try:
        # بدء مؤشر ترابط المهام الخلفية
        # daemon=True يعني أن المؤشر سينتهي عند انتهاء البرنامج الرئيسي
        bg_thread = threading.Thread(target=background_tasks_scheduler, daemon=True)
        bg_thread.start()
        
        logger.info("⏳ البوت قيد التشغيل الآن وينتظر الأوامر...")
        logger.info(f"معرف الأدمن: {ADMIN_ID}")
        logger.info(f"المجموعات المعتمدة: {APPROVED_GROUP_IDS}")
        logger.info(f"مسار قاعدة البيانات: {DB_PATH}")
        logger.info(f"ملف السجل: {LOG_FILE}")

        # إرسال رسالة للأدمن عند بدء التشغيل
        try:
            bot.send_message(ADMIN_ID, "🚀 تم إعادة تشغيل البوت بنجاح وهو الآن متصل!")
        except Exception as startup_msg_err:
            logger.error(f"لم يتمكن من إرسال رسالة بدء التشغيل للأدمن: {startup_msg_err}")

        retry_delay = 5 # ثواني
        max_retry_delay = 300 # 5 دقائق
        while True:
            try:
                bot.infinity_polling(logger_level=logging.WARNING, timeout=20, long_polling_timeout=20) # تعديل مستوى تسجيل infinity_polling
            except requests.exceptions.ConnectionError as e_conn: # خطأ اتصال شائع
                logger.error(f"خطأ اتصال بالشبكة: {e_conn}. إعادة المحاولة بعد {retry_delay} ثانية...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            except telebot.apihelper.ApiTelegramException as e_api:
                 logger.error(f"خطأ API من تيليجرام: {e_api}. إعادة المحاولة بعد {retry_delay} ثانية...")
                 if "Conflict" in str(e_api): # في حالة تشغيل نسخة أخرى من البوت بنفس التوكن
                     logger.critical("خطأ تضارب: يبدو أن هناك نسخة أخرى من البوت تعمل بنفس التوكن. سيتم إيقاف هذه النسخة.")
                     bot.send_message(ADMIN_ID, "🚨 خطأ تضارب! تم إيقاف البوت لأن نسخة أخرى تعمل بنفس التوكن.")
                     sys.exit(1) # إنهاء البرنامج
                 time.sleep(retry_delay)
                 retry_delay = min(retry_delay * 2, max_retry_delay)
            except Exception as e:
                logger.error(f"خطأ غير متوقع في حلقة التشغيل الرئيسية (infinity_polling): {str(e)}", exc_info=True)
                # إبلاغ الأدمن بالخطأ إذا كان فادحًا
                try:
                    bot.send_message(ADMIN_ID, f"🚨 خطأ فادح في البوت: {e}\nأحاول إعادة الاتصال...")
                except Exception as admin_notify_poll_err:
                    logger.error(f"فشل إبلاغ الأدمن بخطأ infinity_polling: {admin_notify_poll_err}")
                
                time.sleep(retry_delay) # انتظار قبل إعادة المحاولة
                retry_delay = min(retry_delay * 2, max_retry_delay) # زيادة مدة الانتظار تدريجيًا
    
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت يدويًا (KeyboardInterrupt).")
        try:
            bot.send_message(ADMIN_ID, "🛑 تم إيقاف البوت يدويًا.")
        except:
            pass
        sys.exit(0)
    except Exception as e_critical: # أخطاء حرجة جدًا تمنع بدء التشغيل
        logger.critical(f"❌ خطأ حرج جدًا منع تشغيل البوت: {str(e_critical)}", exc_info=True)
        try:
            bot.send_message(ADMIN_ID, f"❌ فشل تشغيل البوت بسبب خطأ حرج: {e_critical}")
        except:
            pass
        sys.exit(1)
