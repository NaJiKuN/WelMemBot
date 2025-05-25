#v3.3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)
import random
import string
import os
import json
from datetime import datetime, timedelta

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ثوابت المحادثة
GROUP_ID, NUM_CODES, USER_CODE = range(3)

# تحميل البيانات أو إنشاء ملف جديد إذا لم يكن موجوداً
DATA_FILE = '/home/ec2-user/projects/WelMemBot/data.json'

def load_data():
    if not os.path.exists(DATA_FILE):
        return {'codes': {}, 'used_codes': {}, 'group_settings': {}}
    
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {'codes': {}, 'used_codes': {}, 'group_settings': {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# توليد كود عشوائي
def generate_code(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# أوامر البوت
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        update.message.reply_text(
            "مرحباً أيها المسؤول!\n"
            "لإنشاء أكواد دعوة، استخدم الأمر /generate"
        )
    else:
        update.message.reply_text(
            "مرحباً بك!\n"
            "للاستفادة من البوت، يرجى إدخال كود الدعوة الذي حصلت عليه."
        )
        return USER_CODE

def generate(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        update.message.reply_text("ليس لديك صلاحية استخدام هذا الأمر.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "الرجاء إدخال معرف المجموعة (Group ID) التي تريد إنشاء أكواد لها.\n"
        "يجب أن يبدأ المعرف ب -100 (مثال: -1002329495586)"
    )
    return GROUP_ID

def get_group_id(update: Update, context: CallbackContext) -> int:
    group_id = update.message.text.strip()
    
    try:
        group_id_int = int(group_id)
        if group_id_int >= 0:
            update.message.reply_text("معرف المجموعة يجب أن يبدأ ب -100.")
            return GROUP_ID
    except ValueError:
        update.message.reply_text("معرف المجموعة يجب أن يكون رقماً. مثال: -1002329495586")
        return GROUP_ID
    
    context.user_data['group_id'] = group_id
    update.message.reply_text("كم عدد الأكواد التي تريد إنشاءها؟ (الحد الأقصى 50)")
    return NUM_CODES

def get_num_codes(update: Update, context: CallbackContext) -> int:
    try:
        num_codes = int(update.message.text.strip())
        if num_codes <= 0 or num_codes > 50:
            update.message.reply_text("الرجاء إدخال عدد بين 1 و 50.")
            return NUM_CODES
    except ValueError:
        update.message.reply_text("الرجاء إدخال رقم صحيح.")
        return NUM_CODES
    
    group_id = context.user_data['group_id']
    data = load_data()
    
    if group_id not in data['codes']:
        data['codes'][group_id] = []
    
    new_codes = []
    for _ in range(num_codes):
        code = generate_code()
        data['codes'][group_id].append(code)
        new_codes.append(code)
    
    save_data(data)
    
    update.message.reply_text(
        f"تم إنشاء {num_codes} أكواد للمجموعة {group_id}:\n\n" +
        "\n".join(new_codes) +
        "\n\nسيتم إبطال هذه الأكواد بعد استخدامها مرة واحدة."
    )
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def handle_code_input(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    
    # البحث عن الكود في جميع المجموعات
    found = False
    target_group = None
    
    for group_id, codes in data['codes'].items():
        if user_input in codes:
            found = True
            target_group = group_id
            break
    
    if not found:
        update.message.reply_text("الكود المدخل خاطئ أو غير صالح. حاول إدخال الكود بشكل صحيح.")
        return USER_CODE
    
    # التحقق مما إذا كان الكود مستخدمًا مسبقًا
    if user_input in data.get('used_codes', {}):
        update.message.reply_text("هذا الكود مستخدم مسبقاً.")
        return USER_CODE
    
    # إضافة المستخدم إلى المجموعة
    try:
        context.bot.send_message(
            chat_id=target_group,
            text=f"جارٍ إضافة المستخدم {user.full_name} إلى المجموعة..."
        )
        
        context.bot.add_chat_member(
            chat_id=target_group,
            user_id=user.id,
        )
        
        # وضع الكود كـ مستخدم
        if 'used_codes' not in data:
            data['used_codes'] = {}
        data['used_codes'][user_input] = {
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'used_at': datetime.now().isoformat(),
            'group_id': target_group
        }
        
        # إزالة الكود من القائمة المتاحة
        data['codes'][target_group].remove(user_input)
        save_data(data)
        
        # إرسال رسالة الترحيب في المجموعة
        welcome_message = (
            f"أهلاً وسهلاً بك، {user.full_name}!\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        )
        
        context.bot.send_message(
            chat_id=target_group,
            text=welcome_message
        )
        
        update.message.reply_text(
            "تمت إضافتك إلى المجموعة بنجاح!\n"
            "يمكنك الآن الذهاب إلى المجموعة والبدء في التفاعل."
        )
        
    except Exception as e:
        logger.error(f"Error adding user to group: {e}")
        update.message.reply_text("حدث خطأ أثناء محاولة إضافتك إلى المجموعة. يرجى المحاولة لاحقاً.")
    
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if update and update.effective_message:
        update.effective_message.reply_text("حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.")

def main() -> None:
    # تحميل البيانات عند التشغيل
    if not os.path.exists(os.path.dirname(DATA_FILE)):
        os.makedirs(os.path.dirname(DATA_FILE))
    
    # إنشاء ملف البيانات إذا لم يكن موجوداً
    load_data()
    
    # إنشاء Updater وإعطائه توكن البوت
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    # محادثة إنشاء الأكواد (للمسؤول فقط)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', generate)],
        states={
            GROUP_ID: [MessageHandler(Filters.text & ~Filters.command, get_group_id)],
            NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, get_num_codes)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    dispatcher.add_handler(conv_handler)
    
    # محادثة إدخال الكود (للمستخدمين العاديين)
    user_code_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            USER_CODE: [MessageHandler(Filters.text & ~Filters.command, handle_code_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    dispatcher.add_handler(user_code_handler)
    
    # إضافة معالج الأخطاء
    dispatcher.add_error_handler(error_handler)
    
    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
    ADMIN_ID = 764559466
    main()
