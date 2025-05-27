# -*- coding: utf-8 -*- X3.0
import telebot
import json
import os
import uuid
import time
import fcntl  # لتأمين الملف
from telebot import types
from telebot.apihelper import ApiTelegramException

# --- إعدادات البوت ---
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466
DATA_FILE = "/home/ubuntu/WelMemBot/data.json"
BOT_DIR = "/home/ubuntu/WelMemBot"

# --- الرسالة الترحيبية الافتراضية ---
DEFAULT_WELCOME_MESSAGE = "Welcome, {username}!\nYour membership will automatically expire after one month.\nPlease adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."

# --- تهيئة البوت ---
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')

# --- تحميل/إنشاء ملف البيانات مع قفل ---
def load_data():
    if not os.path.exists(BOT_DIR):
        os.makedirs(BOT_DIR)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                content = f.read()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                if not content:
                    return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}, "user_state": {}}
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Warning: {DATA_FILE} is corrupted or empty. Initializing with default data.")
            return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}, "user_state": {}}
    else:
        return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}, "user_state": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, indent=4, ensure_ascii=False)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# تحميل البيانات عند بدء التشغيل
data = load_data()
if "groups" not in data: data["groups"] = {}
if "welcome_message" not in data: data["welcome_message"] = DEFAULT_WELCOME_MESSAGE
if "admin_state" not in data: data["admin_state"] = {}
if "user_state" not in data: data["user_state"] = {}
save_data(data)

print("Bot started...")

# --- وظائف مساعدة لإدارة الحالة ---
def reset_admin_state(admin_id):
    admin_id_str = str(admin_id)
    data = load_data()
    if admin_id_str in data.get("admin_state", {}):
        del data["admin_state"][admin_id_str]
        save_data(data)

def set_admin_state(admin_id, action, target_group_id=None):
    admin_id_str = str(admin_id)
    data = load_data()
    if "admin_state" not in data: data["admin_state"] = {}
    data["admin_state"][admin_id_str] = {"action": action}
    if target_group_id:
        data["admin_state"][admin_id_str]["target_group_id"] = str(target_group_id)
    save_data(data)

def get_admin_state(admin_id):
    admin_id_str = str(admin_id)
    data = load_data()
    return data.get("admin_state", {}).get(admin_id_str)

def set_user_state(user_id, action):
    user_id_str = str(user_id)
    data = load_data()
    if "user_state" not in data: data["user_state"] = {}
    data["user_state"][user_id_str] = {"action": action}
    save_data(data)

def get_user_state(user_id):
    user_id_str = str(user_id)
    data = load_data()
    return data.get("user_state", {}).get(user_id_str)

def reset_user_state(user_id):
    user_id_str = str(user_id)
    data = load_data()
    if user_id_str in data.get("user_state", {}):
        del data["user_state"][user_id_str]
        save_data(data)

# --- تقسيم الرسائل الطويلة ---
def send_long_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    max_length = 4096
    if len(text) <= max_length:
        try:
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        except ApiTelegramException as e:
            print(f"Error sending message to {chat_id}: {e}")
            bot.send_message(chat_id, "حدث خطأ أثناء إرسال الرسالة. يرجى المحاولة لاحقًا.")
    else:
        parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for i, part in enumerate(parts):
            current_markup = reply_markup if i == len(parts) - 1 else None
            try:
                bot.send_message(chat_id, part, reply_markup=current_markup, parse_mode=parse_mode)
            except ApiTelegramException as e:
                print(f"Error sending message part {i+1} to {chat_id}: {e}")
                bot.send_message(chat_id, "حدث خطأ أثناء إرسال جزء من الرسالة.")

# --- معالج الأمر /start ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    reset_admin_state(user_id)
    reset_user_state(user_id)

    if user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_add_group = types.InlineKeyboardButton("➕ إضافة/اختيار مجموعة", callback_data="admin_select_group")
        btn_manage_codes = types.InlineKeyboardButton("🔑 إدارة الأكواد", callback_data="admin_manage_codes")
        btn_set_welcome = types.InlineKeyboardButton("✉️ تغيير رسالة الترحيب", callback_data="admin_set_welcome")
        markup.add(btn_add_group, btn_manage_codes, btn_set_welcome)
        bot.send_message(ADMIN_ID, "أهلاً بك أيها المسؤول! اختر أحد الخيارات:", reply_markup=markup)
    else:
        set_user_state(user_id, "awaiting_code")
        bot.send_message(user_id, "أهلاً بك! يرجى إرسال كود الدعوة الخاص بك.")

# --- معالج الأمر /help ---
@bot.message_handler(commands=['help'])
def handle_help(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.reply_to(message, "أوامر المسؤول:\n/start - عرض القائمة الرئيسية\n/set_welcome - تغيير رسالة الترحيب\n/copy <code> - نسخ كود معين")
    else:
        bot.reply_to(message, "أهلاً! أرسل كود الدعوة للانضمام إلى المجموعة باستخدام /start ثم إدخال الكود.")

# --- معالج ردود الأزرار للمسؤول ---
@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def handle_admin_callback(call):
    data = load_data()
    admin_id = call.from_user.id
    callback_action = call.data

    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error answering callback query: {e}")

    if callback_action == "admin_select_group":
        groups = data.get("groups", {})
        markup = types.InlineKeyboardMarkup(row_width=1)
        if groups:
            for group_id_str, group_info in groups.items():
                group_name = group_info.get('name', f"المجموعة {group_id_str}")
                btn = types.InlineKeyboardButton(group_name, callback_data=f"admin_manage_group_{group_id_str}")
                markup.add(btn)
        btn_add_new = types.InlineKeyboardButton("➕ إضافة مجموعة جديدة", callback_data="admin_add_new_group")
        markup.add(btn_add_new)
        prompt = "اختر مجموعة لإدارتها أو أضف مجموعة جديدة:" if groups else "لا توجد مجموعات حالياً. أضف مجموعة جديدة:"
        try:
            bot.edit_message_text(prompt, admin_id, call.message.message_id, reply_markup=markup)
        except ApiTelegramException as e:
            if "message to edit not found" in str(e):
                bot.send_message(admin_id, prompt, reply_markup=markup)
            elif "message is not modified" not in str(e):
                print(f"Error editing message (admin_select_group): {e}")
                bot.send_message(admin_id, prompt, reply_markup=markup)

    # ... (باقي معالجات الأزرار بدون تغيير كبير، لكن مع تحسين معالجة الأخطاء)

    elif callback_action == "admin_set_welcome":
        current_welcome = data.get("welcome_message", DEFAULT_WELCOME_MESSAGE)
        prompt = f"الرسالة الترحيبية الحالية هي:\n\n`{current_welcome}`\n\nأرسل الرسالة الجديدة الآن. استخدم `{{username}}` ليتم استبدالها باسم المستخدم."
        try:
            bot.edit_message_text(prompt, admin_id, call.message.message_id, parse_mode='Markdown')
        except ApiTelegramException as e:
            if "message to edit not found" in str(e):
                bot.send_message(admin_id, prompt, parse_mode='Markdown')
            elif "message is not modified" not in str(e):
                print(f"Error editing message (admin_set_welcome): {e}")
                bot.send_message(admin_id, prompt, parse_mode='Markdown')
        set_admin_state(admin_id, "awaiting_welcome_message")

# --- معالج الرسائل النصية للمسؤول ---
@bot.message_handler(func=lambda message: get_admin_state(message.from_user.id) is not None and message.from_user.id == ADMIN_ID, content_types=['text'])
def handle_admin_messages(message):
    data = load_data()
    admin_id = message.from_user.id
    state = get_admin_state(admin_id)
    action = state.get("action")

    if action == "awaiting_group_id":
        try:
            group_id_str = message.text.strip()
            if not group_id_str.startswith("-100") or not group_id_str[1:].isdigit():
                raise ValueError("Invalid group ID format.")
            group_id_int = int(group_id_str)

            # التحقق من صلاحيات البوت
            try:
                chat_info = bot.get_chat(group_id_int)
                group_name = chat_info.title if chat_info.title else f"المجموعة {group_id_str}"
                admins = bot.get_chat_administrators(group_id_int)
                bot_id = bot.get_me().id
                is_admin = any(admin.user.id == bot_id for admin in admins)
                if not is_admin:
                    bot.send_message(admin_id, f"البوت ليس مشرفًا في المجموعة {group_name}. يرجى تعيين البوت كمشرف مع صلاحيات إنشاء روابط الدعوة وإرسال الرسائل.")
                    return
            except ApiTelegramException as e:
                bot.send_message(admin_id, f"لم أتمكن من الوصول إلى المجموعة {group_id_str}. تأكد من أن البوت عضو في المجموعة ولديه الصلاحيات اللازمة. الخطأ: {e}")
                return

            if group_id_str in data.get("groups", {}):
                bot.send_message(admin_id, f"المجموعة *{group_name}* ({group_id_str}) موجودة بالفعل.")
            else:
                data["groups"][group_id_str] = {"codes": {}, "name": group_name}
                save_data(data)
                bot.send_message(admin_id, f"تمت إضافة المجموعة بنجاح: *{group_name}* ({group_id_str})")
            set_admin_state(admin_id, "managing_group", target_group_id=group_id_str)
            show_group_management_options(admin_id, message.message_id + 1, group_id_str)

        except ValueError:
            bot.send_message(admin_id, "معرف المجموعة غير صالح. يجب أن يكون رقمًا ويبدأ بـ -100 (مثال: -100123456789). حاول مرة أخرى.")
        except Exception as e:
            bot.send_message(admin_id, f"حدث خطأ غير متوقع عند إضافة المجموعة: {e}. يرجى المحاولة مرة أخرى.")
            reset_admin_state(admin_id)

    # ... (باقي معالجة الرسائل بدون تغيير كبير)

# --- معالج الرسائل النصية للمستخدمين العاديين ---
@bot.message_handler(func=lambda message: message.from_user.id != ADMIN_ID and get_user_state(message.from_user.id) is not None, content_types=['text'])
def handle_user_code(message):
    user_id = message.from_user.id
    user_info = message.from_user
    state = get_user_state(user_id)
    if state.get("action") != "awaiting_code":
        bot.send_message(user_id, "يرجى إرسال كود الدعوة باستخدام /start أولاً.")
        return

    entered_code = message.text.strip()
    data = load_data()
    code_found = False
    code_valid = False
    target_group_id_str = None

    print(f"User {user_id} ({user_info.username or user_info.first_name}) entered code: {entered_code}")

    for group_id, group_info in data.get("groups", {}):
        if entered_code in group_info.get("codes", {}):
            code_found = True
            code_details = group_info["codes"][entered_code]
            if code_details.get("status") == "new":
                code_valid = True
                target_group_id_str = group_id
                code_details["status"] = "used"
                code_details["user_id"] = user_id
                code_details["username"] = user_info.username or f"{user_info.first_name} {user_info.last_name or ''}".strip()
                code_details["used_time"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                save_data(data)
                print(f"Code {entered_code} validated for user {user_id} for group {target_group_id_str}.")
            break

    if code_valid and target_group_id_str:
        try:
            invite_link = bot.create_chat_invite_link(chat_id=int(target_group_id_str), member_limit=1, expire_date=int(time.time()) + 3600)
            group_name = data["groups"][target_group_id_str].get('name', target_group_id_str)
            bot.send_message(user_id, f"تم التحقق من الكود بنجاح! ✅\n\nيمكنك الآن الانضمام إلى *{group_name}* عبر هذا الرابط (صالح لمدة ساعة واحدة فقط):\n{invite_link.invite_link}")
            print(f"Invite link generated for user {user_id} for group {target_group_id_str}")
        except ApiTelegramException as e:
            print(f"Error creating invite link for group {target_group_id_str}: {e}")
            bot.send_message(user_id, "فشل إنشاء رابط الدعوة. يرجى التواصل مع المسؤول.")
            bot.send_message(ADMIN_ID, f"فشل إنشاء رابط دعوة للمستخدم {user_id} للمجموعة {target_group_id_str}. الخطأ: {e}")
            # إعادة الكود إلى حالة "new"
            data["groups"][target_group_id_str]["codes"][entered_code]["status"] = "new"
            save_data(data)
    elif code_found:
        bot.send_message(user_id, "الكود المدخل غير صحيح أو تم استخدامه مسبقًا. يرجى التحقق من الكود أو طلب كود جديد.")
    else:
        bot.send_message(user_id, "الكود المدخل غير موجود. يرجى التحقق من الكود أو التواصل مع المسؤول.")

    reset_user_state(user_id)

# --- بدء تشغيل البوت ---
if __name__ == '__main__':
    print("Starting polling...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except ApiTelegramException as e:
            print(f"ERROR: Polling failed: {e}")
            if "Too Many Requests" in str(e):
                time.sleep(30)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"Unexpected error in polling: {e}")
            time.sleep(10)
