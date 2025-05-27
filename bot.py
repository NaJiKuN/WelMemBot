# -*- coding: utf-8 -*- M1.0
import telebot
import json
import os
import uuid
import time # لإضافة تأخير بسيط عند الحاجة
from telebot import types

# --- إعدادات البوت ---
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466 # معرف المسؤول الرئيسي
DATA_FILE = "/home/ubuntu/WelMemBot/data.json"
BOT_DIR = "/home/ubuntu/WelMemBot"

# --- الرسالة الترحيبية الافتراضية ---
DEFAULT_WELCOME_MESSAGE = "Welcome, {username}!\nYour membership will automatically expire after one month.\nPlease adhere to the group rules and avoid leaving before the specified period to prevent membership suspension."

# --- تهيئة البوت ---
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown') # استخدام Markdown افتراضيًا

# --- تحميل/إنشاء ملف البيانات ---
def load_data():
    if not os.path.exists(BOT_DIR):
        os.makedirs(BOT_DIR)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}}
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Warning: {DATA_FILE} is corrupted or empty. Initializing with default data.")
            return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}}
    else:
        return {"groups": {}, "welcome_message": DEFAULT_WELCOME_MESSAGE, "admin_state": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# تحميل البيانات عند بدء التشغيل
data = load_data()
if "groups" not in data: data["groups"] = {}
if "welcome_message" not in data: data["welcome_message"] = DEFAULT_WELCOME_MESSAGE
if "admin_state" not in data: data["admin_state"] = {}
save_data(data)

print("Bot started...")

# --- وظائف مساعدة للمسؤول ---
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

# --- معالج الأمر /start ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    reset_admin_state(user_id) # إعادة تعيين أي حالة سابقة للمستخدم/المسؤول

    if user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_add_group = types.InlineKeyboardButton("➕ إضافة/اختيار مجموعة", callback_data="admin_select_group")
        btn_manage_codes = types.InlineKeyboardButton("🔑 إدارة الأكواد", callback_data="admin_manage_codes")
        btn_set_welcome = types.InlineKeyboardButton("✉️ تغيير رسالة الترحيب", callback_data="admin_set_welcome")
        markup.add(btn_add_group, btn_manage_codes, btn_set_welcome)
        bot.send_message(ADMIN_ID, "أهلاً بك أيها المسؤول! اختر أحد الخيارات:", reply_markup=markup)
    else:
        bot.send_message(user_id, "أهلاً بك! يرجى إرسال كود الدعوة الخاص بك.")
        # لا نسجل حالة للمستخدم العادي، ننتظر رسالته التالية مباشرة

# --- معالج ردود الأزرار (Callback Query) للمسؤول ---
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
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e):
                 bot.send_message(admin_id, prompt, reply_markup=markup)
            elif "message is not modified" not in str(e):
                 print(f"Error editing message (admin_select_group): {e}")
                 bot.send_message(admin_id, prompt, reply_markup=markup)

    elif callback_action == "admin_add_new_group":
        prompt = "يرجى إرسال ID المجموعة الجديدة التي تريد إضافتها (مثال: -100123456789)."
        try:
            bot.edit_message_text(prompt, admin_id, call.message.message_id)
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e):
                 bot.send_message(admin_id, prompt)
            elif "message is not modified" not in str(e):
                 print(f"Error editing message (admin_add_new_group): {e}")
                 bot.send_message(admin_id, prompt)
        set_admin_state(admin_id, "awaiting_group_id")

    elif callback_action.startswith("admin_manage_group_"):
        group_id_str = callback_action.split("_")[-1]
        set_admin_state(admin_id, "managing_group", target_group_id=group_id_str)
        show_group_management_options(admin_id, call.message.message_id, group_id_str)

    elif callback_action == "admin_manage_codes":
        groups = data.get("groups", {})
        if not groups:
            prompt = "لا يمكنك إدارة الأكواد قبل إضافة مجموعة واحدة على الأقل. اضغط على '➕ إضافة/اختيار مجموعة' أولاً."
            try:
                bot.edit_message_text(prompt, admin_id, call.message.message_id)
            except telebot.apihelper.ApiTelegramException as e:
                 if "message to edit not found" in str(e):
                      bot.send_message(admin_id, prompt)
                 elif "message is not modified" not in str(e):
                      print(f"Error editing message (admin_manage_codes no groups): {e}")
                      bot.send_message(admin_id, prompt)
        else:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for group_id_str, group_info in groups.items():
                group_name = group_info.get('name', f"المجموعة {group_id_str}")
                btn = types.InlineKeyboardButton(group_name, callback_data=f"admin_manage_codes_for_{group_id_str}")
                markup.add(btn)
            prompt = "اختر المجموعة التي تريد إدارة أكوادها:"
            try:
                bot.edit_message_text(prompt, admin_id, call.message.message_id, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                 if "message to edit not found" in str(e):
                      bot.send_message(admin_id, prompt, reply_markup=markup)
                 elif "message is not modified" not in str(e):
                      print(f"Error editing message (admin_manage_codes select): {e}")
                      bot.send_message(admin_id, prompt, reply_markup=markup)

    elif callback_action.startswith("admin_manage_codes_for_"):
        group_id_str = callback_action.split("_")[-1]
        set_admin_state(admin_id, "managing_group", target_group_id=group_id_str)
        show_group_management_options(admin_id, call.message.message_id, group_id_str)

    elif callback_action == "admin_generate_codes":
        state = get_admin_state(admin_id)
        if state and state.get("action") == "managing_group" and state.get("target_group_id"):
            group_id_str = state["target_group_id"]
            group_name = data.get("groups", {}).get(group_id_str, {}).get('name', group_id_str)
            prompt = f"كم عدد الأكواد التي ترغب في توليدها لـ *{group_name}*؟"
            try:
                bot.edit_message_text(prompt, admin_id, call.message.message_id)
            except telebot.apihelper.ApiTelegramException as e:
                 if "message to edit not found" in str(e):
                      bot.send_message(admin_id, prompt)
                 elif "message is not modified" not in str(e):
                      print(f"Error editing message (admin_generate_codes): {e}")
                      bot.send_message(admin_id, prompt)
            set_admin_state(admin_id, "awaiting_code_count", target_group_id=group_id_str)
        else:
            prompt = "حدث خطأ. يرجى البدء من جديد باختيار مجموعة أولاً."
            try:
                bot.edit_message_text(prompt, admin_id, call.message.message_id)
            except telebot.apihelper.ApiTelegramException as e:
                 if "message to edit not found" in str(e):
                      bot.send_message(admin_id, prompt)
                 elif "message is not modified" not in str(e):
                      print(f"Error editing message (admin_generate_codes error): {e}")
                      bot.send_message(admin_id, prompt)
            reset_admin_state(admin_id)

    elif callback_action == "admin_view_codes":
        state = get_admin_state(admin_id)
        if state and state.get("action") == "managing_group" and state.get("target_group_id"):
            group_id_str = state["target_group_id"]
            display_codes_for_group(admin_id, call.message.message_id, group_id_str)
        else:
            prompt = "حدث خطأ. يرجى البدء من جديد باختيار مجموعة أولاً."
            try:
                bot.edit_message_text(prompt, admin_id, call.message.message_id)
            except telebot.apihelper.ApiTelegramException as e:
                 if "message to edit not found" in str(e):
                      bot.send_message(admin_id, prompt)
                 elif "message is not modified" not in str(e):
                      print(f"Error editing message (admin_view_codes error): {e}")
                      bot.send_message(admin_id, prompt)
            reset_admin_state(admin_id)

    elif callback_action == "admin_set_welcome":
        current_welcome = data.get("welcome_message", DEFAULT_WELCOME_MESSAGE)
        prompt = f"الرسالة الترحيبية الحالية هي:\n\n`{current_welcome}`\n\nأرسل الرسالة الجديدة الآن. استخدم `{{username}}` ليتم استبدالها باسم المستخدم."
        try:
            bot.edit_message_text(prompt, admin_id, call.message.message_id, parse_mode='Markdown')
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e):
                 bot.send_message(admin_id, prompt, parse_mode='Markdown')
            elif "message is not modified" not in str(e):
                 print(f"Error editing message (admin_set_welcome): {e}")
                 bot.send_message(admin_id, prompt, parse_mode='Markdown')
        set_admin_state(admin_id, "awaiting_welcome_message")

    elif callback_action == "admin_back_to_main":
        reset_admin_state(admin_id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_add_group = types.InlineKeyboardButton("➕ إضافة/اختيار مجموعة", callback_data="admin_select_group")
        btn_manage_codes = types.InlineKeyboardButton("🔑 إدارة الأكواد", callback_data="admin_manage_codes")
        btn_set_welcome = types.InlineKeyboardButton("✉️ تغيير رسالة الترحيب", callback_data="admin_set_welcome")
        markup.add(btn_add_group, btn_manage_codes, btn_set_welcome)
        prompt = "أهلاً بك أيها المسؤول! اختر أحد الخيارات:"
        try:
            bot.edit_message_text(prompt, admin_id, call.message.message_id, reply_markup=markup)
        except telebot.apihelper.ApiTelegramException as e:
             if "message to edit not found" in str(e):
                  bot.send_message(admin_id, prompt, reply_markup=markup)
             elif "message is not modified" not in str(e):
                 print(f"Error editing message (admin_back_to_main): {e}")
                 bot.send_message(admin_id, prompt, reply_markup=markup)

# --- دالة عرض خيارات إدارة مجموعة محددة ---
def show_group_management_options(admin_id, message_id, group_id_str):
    data = load_data()
    group_info = data.get("groups", {}).get(group_id_str)
    if not group_info:
        prompt = f"المجموعة {group_id_str} لم تعد موجودة."
        try:
            bot.edit_message_text(prompt, admin_id, message_id)
        except telebot.apihelper.ApiTelegramException as e:
             if "message to edit not found" in str(e):
                  bot.send_message(admin_id, prompt)
             elif "message is not modified" not in str(e):
                  print(f"Error editing message (show_group_management_options group missing): {e}")
                  bot.send_message(admin_id, prompt)
        reset_admin_state(admin_id)
        return

    group_name = group_info.get('name', f"المجموعة {group_id_str}")
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_generate = types.InlineKeyboardButton("➕ توليد أكواد جديدة", callback_data="admin_generate_codes")
    btn_view = types.InlineKeyboardButton("👁️ عرض الأكواد الحالية", callback_data="admin_view_codes")
    btn_back = types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_back_to_main")
    markup.add(btn_generate, btn_view, btn_back)
    prompt = f"إدارة *{group_name}* ({group_id_str}):"
    try:
        bot.edit_message_text(prompt, admin_id, message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as e:
        if "message to edit not found" in str(e):
             bot.send_message(admin_id, prompt, reply_markup=markup)
        elif "message is not modified" not in str(e):
             print(f"Error editing message (show_group_management_options): {e}")
             bot.send_message(admin_id, prompt, reply_markup=markup)

# --- دالة عرض الأكواد لمجموعة محددة ---
def display_codes_for_group(admin_id, message_id, group_id_str):
    data = load_data()
    group_info = data.get("groups", {}).get(group_id_str)
    group_name = group_info.get('name', group_id_str) if group_info else group_id_str

    if not group_info or "codes" not in group_info or not group_info["codes"]:
        prompt = f"لا توجد أكواد لـ *{group_name}* ({group_id_str}) بعد."
        markup = types.InlineKeyboardMarkup()
        btn_back_to_group = types.InlineKeyboardButton("🔙 العودة لإدارة المجموعة", callback_data=f"admin_manage_group_{group_id_str}")
        markup.add(btn_back_to_group)
        try:
            bot.edit_message_text(prompt, admin_id, message_id, reply_markup=markup)
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e):
                 bot.send_message(admin_id, prompt, reply_markup=markup)
            elif "message is not modified" not in str(e):
                 print(f"Error editing message (display_codes_for_group no codes): {e}")
                 bot.send_message(admin_id, prompt, reply_markup=markup)
        return

    codes = group_info["codes"]
    new_codes = {code: info for code, info in codes.items() if info["status"] == "new"}
    used_codes = {code: info for code, info in codes.items() if info["status"] == "used"}

    response_text = f"أكواد *{group_name}* ({group_id_str}):\n\n"
    response_text += f"🟢 *أكواد جديدة ({len(new_codes)}):*\n"
    if new_codes:
        codes_list = "\n".join([f"`/copy {code}`" for code in new_codes.keys()])
        response_text += codes_list + "\n"
    else:
        response_text += "_(لا توجد أكواد جديدة)_\n"

    response_text += f"\n🔴 *أكواد مستخدمة ({len(used_codes)}):*\n"
    if used_codes:
        used_list = "\n".join([f"`{code}` (بواسطة: {info.get('user_id', 'N/A')} بتاريخ: {info.get('used_time', 'N/A')})" for code, info in used_codes.items()])
        response_text += used_list + "\n"
    else:
        response_text += "_(لا توجد أكواد مستخدمة)_\n"

    markup = types.InlineKeyboardMarkup()
    btn_back_to_group = types.InlineKeyboardButton("🔙 العودة لإدارة المجموعة", callback_data=f"admin_manage_group_{group_id_str}")
    markup.add(btn_back_to_group)

    max_length = 4096
    if len(response_text) > max_length:
        try:
            bot.delete_message(admin_id, message_id)
        except Exception as e:
            print(f"Could not delete original message {message_id} before splitting: {e}")
        parts = [response_text[i:i+max_length] for i in range(0, len(response_text), max_length)]
        for i, part in enumerate(parts):
            current_markup = markup if i == len(parts) - 1 else None
            bot.send_message(admin_id, part, reply_markup=current_markup, parse_mode='Markdown')
    else:
        try:
            bot.edit_message_text(response_text, admin_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except telebot.apihelper.ApiTelegramException as e:
             if "message to edit not found" in str(e):
                  bot.send_message(admin_id, response_text, reply_markup=markup, parse_mode='Markdown')
             elif "message is not modified" not in str(e):
                 print(f"Error editing message (display_codes_for_group): {e}")
                 bot.send_message(admin_id, response_text, reply_markup=markup, parse_mode='Markdown')

# --- معالج الرسائل النصية (للردود من المسؤول) ---
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
            group_id_int = int(group_id_str) # للتحقق من صلاحية الـ ID

            # محاولة الحصول على معلومات المجموعة للتحقق من وجودها وصلاحيات البوت
            try:
                 chat_info = bot.get_chat(group_id_int)
                 group_name = chat_info.title if chat_info.title else f"المجموعة {group_id_str}"
                 print(f"Successfully fetched info for group: {group_name} ({group_id_str})")
            except telebot.apihelper.ApiTelegramException as e:
                 bot.send_message(admin_id, f"لم أتمكن من الوصول للمجموعة {group_id_str}. تأكد من أن البوت عضو في المجموعة وأن الـ ID صحيح. الخطأ: {e}")
                 return # لا نغير الحالة

            if group_id_str in data.get("groups", {}):
                 bot.send_message(admin_id, f"المجموعة *{group_name}* ({group_id_str}) موجودة بالفعل.")
                 set_admin_state(admin_id, "managing_group", target_group_id=group_id_str)
                 show_group_management_options(admin_id, message.message_id + 1, group_id_str)
            else:
                if "groups" not in data: data["groups"] = {}
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

    elif action == "awaiting_code_count":
        try:
            count = int(message.text.strip())
            if count <= 0 or count > 500: # تخفيض الحد الأقصى لتجنب المشاكل
                raise ValueError("Invalid code count.")

            group_id_str = state.get("target_group_id")
            if not group_id_str or group_id_str not in data.get("groups", {}):
                bot.send_message(admin_id, "لم يتم تحديد مجموعة صالحة لتوليد الأكواد لها. يرجى البدء من جديد.")
                reset_admin_state(admin_id)
                return

            group_name = data["groups"][group_id_str].get('name', group_id_str)
            generated_codes = []
            all_codes_ever = set()
            for g_id, g_info in data["groups"].items():
                all_codes_ever.update(g_info.get("codes", {}).keys())

            attempts = 0
            max_attempts = count * 3 # محاولات إضافية لتجنب التكرار
            while len(generated_codes) < count and attempts < max_attempts:
                new_code = str(uuid.uuid4())[:8]
                if new_code not in all_codes_ever:
                    data["groups"][group_id_str]["codes"][new_code] = {"status": "new"}
                    generated_codes.append(new_code)
                    all_codes_ever.add(new_code) # أضفه للمجموعة المستخدمة في هذه الجلسة
                attempts += 1

            save_data(data)
            actual_count = len(generated_codes)
            if actual_count == count:
                 bot.send_message(admin_id, f"تم توليد {actual_count} أكواد جديدة بنجاح لـ *{group_name}*.")
            else:
                 bot.send_message(admin_id, f"تم توليد {actual_count} أكواد جديدة فقط لـ *{group_name}* (من أصل {count} مطلوبة) بسبب محاولة تجنب التكرار.")

            if actual_count > 0 and actual_count <= 20: # عرض الأكواد إذا كانت قليلة
                 codes_text = "\n".join([f"`/copy {code}`" for code in generated_codes])
                 bot.send_message(admin_id, f"الأكواد الجديدة:\n{codes_text}", parse_mode='Markdown')
            elif actual_count > 20:
                 bot.send_message(admin_id, "يمكنك عرض جميع الأكواد من خيار 'عرض الأكواد الحالية'.")

            set_admin_state(admin_id, "managing_group", target_group_id=group_id_str)
            show_group_management_options(admin_id, message.message_id + 1, group_id_str)

        except ValueError:
            bot.send_message(admin_id, "الرجاء إدخال عدد صحيح موجب (بين 1 و 500).")
        except Exception as e:
            bot.send_message(admin_id, f"حدث خطأ أثناء توليد الأكواد: {e}. يرجى المحاولة مرة أخرى.")
            reset_admin_state(admin_id)

    elif action == "awaiting_welcome_message":
        new_welcome_message = message.text.strip()
        if not new_welcome_message:
            bot.send_message(admin_id, "لا يمكن تعيين رسالة ترحيب فارغة. حاول مرة أخرى.")
            return
        if len(new_welcome_message) > 1000: # حد لطول الرسالة
             bot.send_message(admin_id, "رسالة الترحيب طويلة جدًا. يرجى اختصارها.")
             return

        data["welcome_message"] = new_welcome_message
        save_data(data)
        bot.send_message(admin_id, f"تم تحديث رسالة الترحيب بنجاح.\nالرسالة الجديدة:\n`{new_welcome_message}`", parse_mode='Markdown')
        reset_admin_state(admin_id)
        # العودة للقائمة الرئيسية
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_add_group = types.InlineKeyboardButton("➕ إضافة/اختيار مجموعة", callback_data="admin_select_group")
        btn_manage_codes = types.InlineKeyboardButton("🔑 إدارة الأكواد", callback_data="admin_manage_codes")
        btn_set_welcome = types.InlineKeyboardButton("✉️ تغيير رسالة الترحيب", callback_data="admin_set_welcome")
        markup.add(btn_add_group, btn_manage_codes, btn_set_welcome)
        bot.send_message(admin_id, "القائمة الرئيسية:", reply_markup=markup)

# --- معالج أمر /copy (لنسخ الكود) ---
@bot.message_handler(commands=['copy'])
def handle_copy_code(message):
    if message.from_user.id == ADMIN_ID:
        try:
            code_to_copy = message.text.split(' ', 1)[1]
            bot.send_message(ADMIN_ID, f"`{code_to_copy}`", parse_mode='Markdown')
        except IndexError:
            bot.send_message(ADMIN_ID, "استخدام غير صحيح. مثال: `/copy 1a2b3c4d`")
        except Exception as e:
             bot.send_message(ADMIN_ID, f"حدث خطأ: {e}")

# --- معالج الرسائل النصية العادية (للمستخدمين العاديين الذين يرسلون الكود) ---
@bot.message_handler(func=lambda message: message.from_user.id != ADMIN_ID and get_admin_state(message.from_user.id) is None, content_types=['text'])
def handle_user_code(message):
    user_id = message.from_user.id
    user_info = message.from_user
    entered_code = message.text.strip()
    data = load_data()
    code_found = False
    code_valid = False
    target_group_id_str = None

    print(f"User {user_id} ({user_info.username or user_info.first_name}) entered code: {entered_code}")

    for group_id, group_info in data.get("groups", {}).items():
        if entered_code in group_info.get("codes", {}):
            code_found = True
            code_details = group_info["codes"][entered_code]
            if code_details.get("status") == "new":
                code_valid = True
                target_group_id_str = group_id
                # تحديث حالة الكود مباشرة
                code_details["status"] = "used"
                code_details["user_id"] = user_id
                code_details["username"] = user_info.username or f"{user_info.first_name} {user_info.last_name or ''}".strip()
                code_details["used_time"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                save_data(data)
                print(f"Code {entered_code} validated for user {user_id} for group {target_group_id_str}. Status updated.")
            else:
                # الكود موجود ولكنه مستخدم
                print(f"Code {entered_code} found but already used by {code_details.get('user_id')}.")
            break # توقف عن البحث بمجرد العثور على الكود

    if code_valid and target_group_id_str:
        try:
            # ملاحظة: الإضافة المباشرة غير ممكنة، سننشئ رابط دعوة لمرة واحدة
            # يتطلب أن يكون البوت مشرفاً في المجموعة ولديه صلاحية إنشاء روابط دعوة
            invite_link = bot.create_chat_invite_link(chat_id=int(target_group_id_str), member_limit=1)
            group_name = data["groups"][target_group_id_str].get('name', target_group_id_str)
            bot.send_message(user_id, f"تم التحقق من الكود بنجاح! ✅\n\nيمكنك الآن الانضمام إلى *{group_name}* عبر هذا الرابط (صالح للاستخدام مرة واحدة فقط وينتهي قريباً):\n{invite_link.invite_link}")
            print(f"Invite link generated and sent to user {user_id} for group {target_group_id_str}")
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Error creating invite link for group {target_group_id_str}: {e}")
            bot.send_message(user_id, "حدث خطأ أثناء محاولة إنشاء رابط الدعوة للمجموعة. يرجى التواصل مع المسؤول.")
            # يجب إعادة حالة الكود إلى 'new' لأن المستخدم لم يتمكن من الحصول على الرابط؟
            # هذا يعتمد على السياسة المطلوبة. للتبسيط، سنترك الكود مستخدماً.
            # data["groups"][target_group_id_str]["codes"][entered_code]["status"] = "new"
            # save_data(data)
        except Exception as e:
            print(f"Unexpected error processing valid code for user {user_id}: {e}")
            bot.send_message(user_id, "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو التواصل مع المسؤول.")

    elif code_found: # الكود موجود ولكنه غير صالح (مستخدم)
        bot.send_message(user_id, "The entered code is incorrect or has already been used. Please try entering the code correctly.")
        print(f"Invalid code message sent to user {user_id} (code used).")
    else: # الكود غير موجود أصلاً
        bot.send_message(user_id, "The entered code is incorrect or has already been used. Please try entering the code correctly.")
        print(f"Invalid code message sent to user {user_id} (code not found).")

# --- معالج الأعضاء الجدد في المجموعات التي يديرها البوت ---
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    data = load_data()
    chat_id_str = str(message.chat.id)

    # تحقق أولاً إذا كانت هذه المجموعة مُدارة بواسطة البوت
    if chat_id_str not in data.get("groups", {}):
        return # تجاهل المجموعات غير المسجلة

    # احصل على الرسالة الترحيبية
    welcome_message_template = data.get("welcome_message", DEFAULT_WELCOME_MESSAGE)

    # رحب بكل عضو جديد انضم في هذه الرسالة
    for new_member in message.new_chat_members:
        # تجنب الترحيب بالبوت نفسه إذا تمت إضافته
        if new_member.id == bot.get_me().id:
            continue

        user_name = new_member.username or f"{new_member.first_name} {new_member.last_name or ''}".strip()
        # استبدال {username} في الرسالة
        welcome_message = welcome_message_template.replace("{username}", f"@{user_name}" if new_member.username else user_name)

        try:
            bot.send_message(message.chat.id, welcome_message)
            print(f"Sent welcome message to {user_name} in group {chat_id_str}")
        except Exception as e:
            print(f"Error sending welcome message to group {chat_id_str}: {e}")
            # قد نرسل رسالة للمسؤول لإعلامه بالمشكلة
            try:
                 bot.send_message(ADMIN_ID, f"فشل إرسال رسالة الترحيب في المجموعة {chat_id_str}. الخطأ: {e}")
            except Exception as admin_err:
                 print(f"Failed to notify admin about welcome message error: {admin_err}")

# --- أمر تغيير رسالة الترحيب (للمسؤول فقط) ---
@bot.message_handler(commands=['set_welcome'])
def handle_set_welcome_command(message):
     user_id = message.from_user.id
     if user_id == ADMIN_ID:
         current_welcome = data.get("welcome_message", DEFAULT_WELCOME_MESSAGE)
         bot.send_message(admin_id, f"الرسالة الترحيبية الحالية هي:\n\n`{current_welcome}`\n\nأرسل الرسالة الجديدة الآن. استخدم `{{username}}` ليتم استبدالها باسم المستخدم.", parse_mode='Markdown')
         set_admin_state(admin_id, "awaiting_welcome_message")
     else:
         bot.reply_to(message, "هذا الأمر مخصص للمسؤول فقط.")

# --- بدء تشغيل البوت ---
if __name__ == '__main__':
    print("Starting polling...")
    # مسح الحالات العالقة عند إعادة التشغيل (اختياري ولكن جيد)
    # data["admin_state"] = {}
    # save_data(data)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"ERROR: Polling failed: {e}")
            print("Restarting polling in 10 seconds...")
            time.sleep(10)

