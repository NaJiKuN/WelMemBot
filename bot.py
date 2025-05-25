# x1.0
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
import random
import string
from datetime import datetime, timedelta
import json
import os

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات البوت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
GROUP_ID = -1002329495586
ADMIN_ID = 764559466

# حالات المحادثة
GET_GROUP_ID, GET_NUM_CODES, GET_USER_CODE = range(3)

# مسار ملف البيانات
DATA_FILE = '/home/ec2-user/projects/WelMemBot/codes_data.json'

# تهيئة ملف البيانات
def init_data_file():
    """Initialize the data file if it doesn't exist."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({"codes": {}, "used_codes": {}}, f)

# تحميل البيانات
def load_data():
    """Load data from the JSON file."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading data file: {e}")
        return {"codes": {}, "used_codes": {}}

# حفظ البيانات
def save_data(data):
    """Save data to the JSON file."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving data file: {e}")

# التحقق من صلاحيات البوت
def check_bot_permissions(context: CallbackContext, chat_id: int) -> bool:
    """Check if the bot has permission to add members to the group."""
    try:
        bot_member = context.bot.get_chat_member(chat_id=chat_id, user_id=context.bot.id)
        return bot_member.can_invite_users
    except Exception as e:
        logger.error(f"Error checking bot permissions: {e}")
        return False

# بدء المحادثة
def start(update: Update, context: CallbackContext) -> int:
    """Handle the /start command for both admin and users."""
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        update.message.reply_text(
            "مرحباً يا مسؤول!\n"
            "اختر أحد الخيارات:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("توليد أكواد جديدة", callback_data='generate_codes')],
                [InlineKeyboardButton("عرض الأكواد المتاحة", callback_data='show_codes')]
            ])
        )
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "مرحباً بك!\n"
            "الرجاء إدخال الكود الذي حصلت عليه للانضمام إلى المجموعة."
        )
        return GET_USER_CODE

# معالجة الأزرار
def button_callback(update: Update, context: CallbackContext) -> int:
    """Handle button callbacks for admin actions."""
    query = update.callback_query
    query.answer()
    
    if query.data == 'generate_codes':
        query.edit_message_text("الرجاء إدخال ID المجموعة التي تريد توليد أكواد لها:")
        return GET_GROUP_ID
    elif query.data == 'show_codes':
        data = load_data()
        active_codes = {k: v for k, v in data['codes'].items() if k not in data['used_codes']}
        
        if not active_codes:
            query.edit_message_text("لا توجد أكواد متاحة حالياً.")
        else:
            message = "الأكواد المتاحة:\n"
            for code, details in active_codes.items():
                message += f"- الكود: {code} (للمجموعة: {details['group_id']})\n"
            query.edit_message_text(message)
        return ConversationHandler.END

# الحصول على ID المجموعة
def get_group_id(update: Update, context: CallbackContext) -> int:
    """Handle group ID input for code generation."""
    try:
        group_id = int(update.message.text)
        if not check_bot_permissions(context, group_id):
            update.message.reply_text("البوت ليس لديه صلاحية إضافة أعضاء إلى هذه المجموعة. الرجاء منح البوت الصلاحيات المطلوبة.")
            return ConversationHandler.END
        context.user_data['group_id'] = group_id
        update.message.reply_text("كم عدد الأكواد التي تريد توليدها؟")
        return GET_NUM_CODES
    except ValueError:
        update.message.reply_text("الرجاء إدخال رقم صحيح لـ ID المجموعة.")
        return GET_GROUP_ID

# الحصول على عدد الأكواد
def get_num_codes(update: Update, context: CallbackContext) -> int:
    """Handle the number of codes to generate."""
    try:
        num_codes = int(update.message.text)
        if num_codes <= 0:
            update.message.reply_text("الرجاء إدخال عدد أكبر من الصفر.")
            return GET_NUM_CODES
        context.user_data['num_codes'] = num_codes
        return generate_codes(update, context)
    except ValueError:
        update.message.reply_text("الرجاء إدخال رقم صحيح.")
        return GET_NUM_CODES

# توليد الأكواد
def generate_codes(update: Update, context: CallbackContext) -> int:
    """Generate random codes for the specified group."""
    group_id = context.user_data['group_id']
    num_codes = context.user_data['num_codes']
    
    data = load_data()
    
    for _ in range(num_codes):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while code in data['codes']:  # التأكد من عدم تكرار الكود
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        data['codes'][code] = {
            'group_id': group_id,
            'generated_at': datetime.now().isoformat()
        }
    
    save_data(data)
    
    update.message.reply_text(
        f"تم توليد {num_codes} كود بنجاح للمجموعة {group_id}.\n"
        "يمكنك عرض الأكواد المتاحة باستخدام الأمر /show_codes"
    )
    
    return ConversationHandler.END

# معالجة كود المستخدم
def get_user_code(update: Update, context: CallbackContext) -> int:
    """Handle user code input and add them to the group."""
    user_code = update.message.text.strip().upper()
    data = load_data()
    
    if user_code in data['used_codes']:
        update.message.reply_text("هذا الكود تم استخدامه مسبقاً.")
        return GET_USER_CODE
    
    if user_code not in data['codes']:
        update.message.reply_text("الكود المدخل خاطئ. حاول إدخال الكود بشكل صحيح.")
        return GET_USER_CODE
    
    group_id = data['codes'][user_code]['group_id']
    user = update.effective_user
    
    # التحقق من أن المستخدم ليس عضواً بالفعل
    try:
        chat_member = context.bot.get_chat_member(chat_id=group_id, user_id=user.id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            update.message.reply_text("أنت بالفعل عضو في المجموعة!")
            return ConversationHandler.END
    except Exception:
        pass  # المستخدم ليس عضواً، يمكن المتابعة
    
    # التحقق من صلاحيات البوت
    if not check_bot_permissions(context, group_id):
        update.message.reply_text("البوت ليس لديه صلاحية إضافة أعضاء إلى المجموعة. الرجاء التواصل مع المسؤول.")
        return ConversationHandler.END
    
    try:
        # إضافة المستخدم إلى المجموعة
        context.bot.add_chat_member(
            chat_id=group_id,
            user_id=user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
        )
        
        # تسجيل الكود كمستخدم
        data['used_codes'][user_code] = {
            'user_id': user.id,
            'username': user.username or user.first_name,
            'used_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
        }
        save_data(data)
        
        # إرسال رسالة ترحيبية في المجموعة
        welcome_message = (
            f"أهلاً وسهلاً بك، {user.username or user.first_name}!\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        )
        context.bot.send_message(
            chat_id=group_id,
            text=welcome_message
        )
        
        update.message.reply_text("تمت إضافتك إلى المجموعة بنجاح!")
        
    except Exception as e:
        logger.error(f"Error adding user {user.id} to group {group_id}: {e}")
        update.message.reply_text("حدث خطأ أثناء محاولة إضافتك إلى المجموعة. الرجاء التواصل مع المسؤول.")
    
    return ConversationHandler.END

# عرض الأكواد
def show_codes(update: Update, context: CallbackContext) -> None:
    """Show available codes to the admin."""
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("هذا الأمر متاح للمسؤول فقط.")
        return
    
    data = load_data()
    active_codes = {k: v for k, v in data['codes'].items() if k not in data['used_codes']}
    
    if not active_codes:
        update.message.reply_text("لا توجد أكواد متاحة حالياً.")
    else:
        message = "الأكواد المتاحة:\n"
        for code, details in active_codes.items():
            message += f"- الكود: {code} (للمجموعة: {details['group_id']})\n"
        update.message.reply_text(message)

# إلغاء المحادثة
def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the ongoing conversation."""
    update.message.reply_text('تم إلغاء العملية.')
    return ConversationHandler.END

# معالجة الأخطاء
def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors during bot operation."""
    logger.error(msg="حدث خطأ في البوت:", exc_info=context.error)
    if update and update.effective_message:
        update.effective_message.reply_text('حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.')

def main() -> None:
    """Main function to start the bot."""
    init_data_file()
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # معالج المحادثة للمسؤول
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start, Filters.user(user_id=ADMIN_ID))],
        states={
            GET_GROUP_ID: [MessageHandler(Filters.text & ~Filters.command, get_group_id)],
            GET_NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, get_num_codes)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # معالج المحادثة للمستخدم العادي
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start, ~Filters.user(user_id=ADMIN_ID))],
        states={
            GET_USER_CODE: [MessageHandler(Filters.text & ~Filters.command, get_user_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # إضافة المعالجات
    dispatcher.add_handler(admin_conv_handler)
    dispatcher.add_handler(user_conv_handler)
    dispatcher.add_handler(CommandHandler('show_codes', show_codes))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    dispatcher.add_handler(error_handler)

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
