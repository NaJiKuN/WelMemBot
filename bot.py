# v3.8
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

# إعدادات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
DB_PATH = '/home/ec2-user/projects/WelMemBot/codes.db'
LOG_FILE = '/home/ec2-user/projects/WelMemBot/bot.log'

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
                             expire_time TEXT, 
                             used INTEGER DEFAULT 0)''')
                conn.commit()
            logger.info("تم تهيئة قاعدة البيانات بنجاح")
        except Exception as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {str(e)}")
            raise
    
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
            chat = bot_instance.get_chat(chat_id)
            bot_member = bot_instance.get_chat_member(chat_id, bot_instance.get_me().id)
            
            required_permissions = {
                'can_invite_users': bot_member.can_invite_users,
                'can_send_messages': bot_member.can_send_messages,
                'status': bot_member.status
            }
            
            logger.info(f"صلاحيات البوت في المجموعة {chat_id}: {required_permissions}")
            
            if bot_member.status not in ['administrator', 'creator']:
                logger.warning(f"البوت ليس مشرفًا في المجموعة {chat_id}")
                return False, "البوت يجب أن يكون مشرفاً في المجموعة"
                
            if not bot_member.can_invite_users:
                logger.warning(f"البوت لا يملك صلاحية إضافة أعضاء في المجموعة {chat_id}")
                return False, "البوت يحتاج صلاحية إضافة أعضاء"
                
            return True, "الصلاحيات كافية"
            
        except telebot.apihelper.ApiTelegramException as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg:
                return False, "المجموعة غير موجودة"
            elif "bot is not a member" in error_msg:
                return False, "البوت ليس عضواً في المجموعة"
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
        codes = []
        for _ in range(count):
            code = CodeGenerator.generate_code()
            try:
                db_manager.execute_query(
                    "INSERT INTO codes (code, group_id) VALUES (?, ?)",
                    (code, group_id)
                )
                codes.append(code)
            except sqlite3.IntegrityError:
                continue  # إذا كان الكود موجوداً بالفعل، نكرر المحاولة
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
            logger.error(f"خطأ في إنشاء رابط الدعوة: {str(e)}")
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
            # التحقق من صحة الكود
            result = db_manager.execute_query(
                """SELECT group_id FROM codes 
                WHERE code = ? AND used = 0""",
                (code,),
                fetch=True
            )
            
            if not result:
                return False, "الكود غير صالح أو مستخدم من قبل"
            
            group_id = result[0]['group_id']
            
            # التحقق من صلاحيات البوت
            success, msg = BotPermissions.check_bot_permissions(bot_instance, group_id)
            if not success:
                return False, msg
            
            # إنشاء رابط الدعوة
            invite_link, expire_time = InviteManager.create_invite_link(
                bot_instance, group_id, user_id, code)
            
            if not invite_link:
                return False, "فشل في إنشاء رابط الدعوة"
            
            # تخزين معلومات الرابط
            link_data = (
                invite_link, group_id, user_id, code,
                datetime.now().isoformat(), expire_time
            )
            if not InviteManager.store_invite_link(db_manager, link_data):
                return False, "فشل في حفظ رابط الدعوة"
            
            # تحديث حالة الكود
            db_manager.execute_query(
                """UPDATE codes SET used = 1, 
                user_id = ? 
                WHERE code = ?""",
                (user_id, code)
            )
            
            return True, invite_link
            
        except Exception as e:
            logger.error(f"خطأ في معالجة الكود: {str(e)}")
            return False, f"حدث خطأ: {str(e)}"
    
    @staticmethod
    def send_welcome_message(bot_instance, db_manager, chat_id, user_id):
        """إرسال رسالة ترحيبية عند الانضمام"""
        try:
            username = bot_instance.get_chat(user_id).first_name or f"User_{user_id}"
            welcome_msg = f"""Welcome, {username}!
Your membership will automatically expire after one month.
Please adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."""
            
            # حفظ تاريخ الانضمام
            db_manager.execute_query(
                """INSERT OR REPLACE INTO memberships 
                (user_id, group_id, join_date) 
                VALUES (?, ?, ?)""",
                (user_id, chat_id, datetime.now().isoformat())
            )
            
            bot_instance.send_message(chat_id, welcome_msg)
            return True
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة الترحيب: {str(e)}")
            return False
    
    @staticmethod
    def notify_expired_memberships(bot_instance, db_manager):
        """إرسال إشعارات للأعضاء المنتهية عضويتهم"""
        try:
            # الأعضاء الذين انتهت عضويتهم ولم يتم إشعار المسؤول بعد
            expired_members = db_manager.execute_query(
                """SELECT user_id, group_id, join_date 
                FROM memberships 
                WHERE join_date < ? AND notified = 0""",
                ((datetime.now() - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for member in expired_members:
                try:
                    username = bot_instance.get_chat(member['user_id']).first_name or f"User_{member['user_id']}"
                    bot_instance.send_message(
                        ADMIN_ID,
                        f"تم إنهاء عضوية العضو: {username} (ID: {member['user_id']})\n"
                        f"المجموعة: {member['group_id']}\n"
                        f"تاريخ الانضمام: {member['join_date']}"
                    )
                    
                    # تحديث حالة الإشعار
                    db_manager.execute_query(
                        """UPDATE memberships 
                        SET notified = 1 
                        WHERE user_id = ? AND group_id = ?""",
                        (member['user_id'], member['group_id'])
                    )
                    
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

def get_group_id(message):
    """الحصول على معرف المجموعة من الأدمن"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "غير مصرح لك باستخدام هذا الأمر!")
        return
    
    group_id = message.text.strip()
    logger.info(f"معرف المجموعة المدخل: {group_id}")
    
    try:
        # التحقق من أن البوت موجود في المجموعة
        chat = bot.get_chat(group_id)
        
        # التحقق من صلاحيات البوت
        success, msg = BotPermissions.check_bot_permissions(bot, group_id)
        if not success:
            bot.reply_to(message, f"خطأ في الصلاحيات: {msg}")
            return
        
        # حفظ المجموعة في قاعدة البيانات
        db_manager.execute_query(
            "INSERT OR REPLACE INTO groups (group_id, welcome_message, is_private) VALUES (?, ?, ?)",
            (group_id, "Welcome to the group!", int(chat.type in ['group', 'supergroup']))
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
    
    try:
        num_codes = int(message.text.strip())
        if num_codes <= 0:
            bot.reply_to(message, "يرجى إدخال عدد صحيح أكبر من 0.")
            return
        
        codes = CodeGenerator.generate_multiple_codes(db_manager, group_id, num_codes)
        if not codes:
            bot.reply_to(message, "حدث خطأ أثناء توليد الأكواد. يرجى المحاولة مرة أخرى.")
            return
            
        # تنسيق الأكواد لسهولة النسخ
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
        # الحصول على جميع المجموعات
        groups = db_manager.execute_query(
            "SELECT group_id FROM groups",
            fetch=True
        )
        
        if not groups:
            bot.reply_to(message, "لا توجد مجموعات مسجلة.")
            return
            
        markup = InlineKeyboardMarkup()
        for group in groups:
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
    try:
        # الأكواد المستخدمة وغير المستخدمة
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
        
        # روابط الدعوة
        invite_links = InviteManager.get_invite_links(db_manager, group_id)
        
        # بناء الرسالة
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
                msg += (f"- الرابط: {link['link']}\n"
                       f"  الكود: {link['code']}\n"
                       f"  المستخدم: {link['user_id']}\n"
                       f"  الحالة: {status}\n"
                       f"  الإنتهاء: {datetime.fromtimestamp(link['expire_time'])}\n\n")
        else:
            msg += "لا توجد روابط دعوة"
        
        bot.reply_to(message, msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ: {str(e)}")
        logger.error(f"خطأ في عرض معلومات المجموعة: {str(e)}")

def check_code(message):
    """التحقق من الكود المدخل من المستخدم"""
    code = message.text.strip().upper()  # تحويل إلى أحرف كبيرة
    user_id = message.from_user.id
    username = message.from_user.first_name or "عضو جديد"
    logger.info(f"الكود المدخل من المستخدم {user_id}: {code}")
    
    success, result = MembershipManager.process_code(bot, db_manager, user_id, code)
    
    if success:
        bot.reply_to(message, 
                    f"مرحبًا {username}!\n\n"
                    f"رابط الانضمام إلى المجموعة (صالح لمدة 24 ساعة):\n{result}\n\n"
                    "سيتم إنهاء عضويتك بعد شهر تلقائيًا.")
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
        logger.info(f"تم تحديث رسالة الترحيب للمجموعة {group_id}")
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
            
            # إرسال رسالة الترحيب
            MembershipManager.send_welcome_message(bot, db_manager, chat_id, user_id)
            
    except Exception as e:
        logger.error(f"خطأ في معالجة العضو الجديد: {str(e)}")

# ===== الوظائف الخلفية =====

def check_expired_links_and_memberships():
    """فحص الروابط والعضويات المنتهية الصلاحية"""
    while True:
        try:
            now = datetime.now()
            
            # حذف روابط الدعوة المنتهية
            expired_links = db_manager.execute_query(
                "SELECT link FROM invite_links WHERE expire_time < ? AND used = 0",
                (now.timestamp(),),
                fetch=True
            )
            
            for link in expired_links:
                db_manager.execute_query(
                    "UPDATE invite_links SET used = 1 WHERE link = ?",
                    (link['link'],)
                )
            
            # حذف العضويات المنتهية (بعد 30 يومًا)
            expired_members = db_manager.execute_query(
                "SELECT user_id, group_id FROM memberships WHERE join_date < ?",
                ((now - timedelta(days=30)).isoformat(),),
                fetch=True
            )
            
            for member in expired_members:
                try:
                    bot.kick_chat_member(member['group_id'], member['user_id'])
                    db_manager.execute_query(
                        "DELETE FROM memberships WHERE user_id = ? AND group_id = ?",
                        (member['user_id'], member['group_id'])
                    )
                    logger.info(f"تم إزالة العضو المنتهية عضويته {member['user_id']} من المجموعة {member['group_id']}")
                except Exception as e:
                    logger.error(f"خطأ في إزالة العضو {member['user_id']}: {str(e)}")
            
            # إرسال إشعارات للأعضاء المنتهية عضويتهم
            MembershipManager.notify_expired_memberships(bot, db_manager)
            
            time.sleep(3600)  # التحقق كل ساعة
            
        except Exception as e:
            logger.error(f"خطأ في الفحص الخلفي: {str(e)}")
            time.sleep(3600)

# بدء البوت
if __name__ == '__main__':
    try:
        # بدء الوظائف الخلفية في خيط منفصل
        bg_thread = threading.Thread(target=check_expired_links_and_memberships, daemon=True)
        bg_thread.start()
        
        logger.info("جاري تشغيل البوت...")
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("إيقاف البوت...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
        sys.exit(1)
