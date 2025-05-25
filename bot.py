import os
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
import json
import random
import string
from datetime import datetime, timedelta

# تهيئة السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات التكوين
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
GROUP_ID = -1002329495586
ADMIN_ID = 764559466

# حالات المحادثة
GROUP_LINK, NUM_CODES, USER_CODE = range(3)

# مسار ملف البيانات
DATA_FILE = '/home/ec2-user/projects/WelMemBot/bot_data.json'

# تحميل البيانات من الملف
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        'invite_links': {},
        'codes': {},
        'used_codes': set(),
        'group_settings': {}
    }

# حفظ البيانات إلى الملف
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# توليد كود فريد
def generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# معالج الأمر /start
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        update.message.reply_text(
            "مرحبًا يا مسؤول! 👋\n"
            "استخدم /generate لإنشاء أكواد دعوة جديدة.\n"
            "استخدم /stats لعرض إحصائيات الأكواد."
        )
    else:
        update.message.reply_text(
            "مرحبًا! 👋\n"
            "أدخل كود الدعوة الخاص بك للانضمام إلى المجموعة."
        )
        return USER_CODE

# بدء عملية إنشاء الأكواد
def generate_codes(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("عفواً، هذا الأمر للمسؤولين فقط.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "أدخل رابط الدعوة للمجموعة:\n"
        "(يجب أن يكون الرابط بصيغة https://t.me/joinchat/xxxxxx)"
    )
    return GROUP_LINK

# معالج رابط الدعوة
def group_link(update: Update, context: CallbackContext) -> int:
    link = update.message.text.strip()
    if not link.startswith('https://t.me/joinchat/'):
        update.message.reply_text("رابط غير صالح! يرجى إدخال رابط دعوة صالح.")
        return GROUP_LINK
    
    context.user_data['invite_link'] = link
    update.message.reply_text("كم عدد أكواد الدعوة التي تريد إنشاءها؟")
    return NUM_CODES

# معالج عدد الأكواد
def num_codes(update: Update, context: CallbackContext) -> int:
    try:
        num = int(update.message.text)
        if num <= 0 or num > 100:
            update.message.reply_text("الرجاء إدخال عدد بين 1 و 100.")
            return NUM_CODES
    except ValueError:
        update.message.reply_text("الرجاء إدخال رقم صحيح.")
        return NUM_CODES
    
    invite_link = context.user_data['invite_link']
    data = load_data()
    
    # إنشاء الأكواد
    codes = []
    for _ in range(num):
        code = generate_code()
        while code in data['codes']:
            code = generate_code()
        
        data['codes'][code] = {
            'invite_link': invite_link,
            'created_at': datetime.now().isoformat(),
            'used': False,
            'group_id': GROUP_ID
        }
        codes.append(code)
    
    # حفظ البيانات
    save_data(data)
    
    # إرسال الأكواد للمسؤول
    update.message.reply_text(
        f"تم إنشاء {num} كود دعوة:\n\n" +
        "\n".join(codes) +
        "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة."
    )
    
    return ConversationHandler.END

# معالج إدخال الكود من قبل المستخدم
def user_code(update: Update, context: CallbackContext) -> int:
    code = update.message.text.upper().strip()
    data = load_data()
    
    if code in data['used_codes']:
        update.message.reply_text("هذا الكود تم استخدامه مسبقًا.")
        return USER_CODE
    
    if code not in data['codes']:
        update.message.reply_text("الكود المدخل خاطئ. حاول إدخال الكود بشكل صحيح.")
        return USER_CODE
    
    code_info = data['codes'][code]
    
    try:
        # إضافة المستخدم إلى المجموعة
        context.bot.unban_chat_member(
            chat_id=code_info['group_id'],
            user_id=update.effective_user.id
        )
        
        # إرسال رسالة ترحيبية في المجموعة
        welcome_message = (
            f"أهلاً وسهلاً بك، {update.effective_user.first_name}!\n\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        )
        
        context.bot.send_message(
            chat_id=code_info['group_id'],
            text=welcome_message
        )
        
        # تحديث البيانات
        data['used_codes'].add(code)
        data['codes'][code]['used'] = True
        data['codes'][code]['used_by'] = update.effective_user.id
        data['codes'][code]['used_at'] = datetime.now().isoformat()
        save_data(data)
        
        update.message.reply_text(
            "تمت إضافتك إلى المجموعة بنجاح! 🎉\n"
            "يمكنك الآن الذهاب إلى المجموعة."
        )
        
    except Exception as e:
        logger.error(f"Error adding user to group: {e}")
        update.message.reply_text(
            "حدث خطأ أثناء محاولة إضافتك إلى المجموعة. يرجى المحاولة لاحقًا."
        )
    
    return ConversationHandler.END

# عرض إحصائيات الأكواد
def stats(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("عفواً، هذا الأمر للمسؤولين فقط.")
        return
    
    data = load_data()
    total_codes = len(data['codes'])
    used_codes = len(data['used_codes'])
    
    update.message.reply_text(
        f"إحصائيات الأكواد:\n\n"
        f"إجمالي الأكواد: {total_codes}\n"
        f"الأكواد المستخدمة: {used_codes}\n"
        f"الأكواد المتاحة: {total_codes - used_codes}"
    )

# إلغاء المحادثة
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# الدالة الرئيسية
def main() -> None:
    # إنشاء Updater وتمرير توكن البوت
    updater = Updater(TOKEN)

    # الحصول على dispatcher لتسجيل المعالجات
    dispatcher = updater.dispatcher

    # معالجات المحادثة للمسؤول
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', generate_codes)],
        states={
            GROUP_LINK: [MessageHandler(Filters.text & ~Filters.command, group_link)],
            NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, num_codes)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # معالجة إدخال الكود من قبل المستخدم
    user_code_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, user_code)],
        states={
            USER_CODE: [MessageHandler(Filters.text & ~Filters.command, user_code)],
        },
        fallbacks=[],
    )

    # تسجيل المعالجات
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('stats', stats))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(user_code_handler)

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
