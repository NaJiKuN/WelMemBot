#v2.6
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
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

# تهيئة ملف البيانات إذا لم يكن موجوداً
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({"codes": {}, "used_codes": {}}, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

async def check_bot_permissions(context: CallbackContext, chat_id: int) -> bool:
    """التحقق من صلاحيات البوت في المجموعة"""
    try:
        chat = await context.bot.get_chat(chat_id)
        bot_member = await chat.get_member(context.bot.id)
        
        # التحقق من الصلاحيات المطلوبة
        if not bot_member.can_invite_users:
            logger.error(f"البوت لا يملك صلاحية إضافة أعضاء في المجموعة {chat_id}")
            return False
        if not bot_member.can_send_messages:
            logger.error(f"البوت لا يملك صلاحية إرسال رسائل في المجموعة {chat_id}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"خطأ في التحقق من صلاحيات البوت: {e}")
        return False

async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "مرحباً يا مسؤول!\n"
            "اختر أحد الخيارات:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("توليد أكواد جديدة", callback_data='generate_codes')],
                [InlineKeyboardButton("عرض الأكواد المتاحة", callback_data='show_codes')]
            ])
        )
    else:
        await update.message.reply_text(
            "مرحباً بك!\n"
            "الرجاء إدخال الكود الذي حصلت عليه للانضمام إلى المجموعة."
        )
        return GET_USER_CODE

async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'generate_codes':
        await query.edit_message_text("الرجاء إدخال ID المجموعة التي تريد توليد أكواد لها:")
        return GET_GROUP_ID
    elif query.data == 'show_codes':
        data = load_data()
        active_codes = {k: v for k, v in data['codes'].items() if k not in data['used_codes']}
        
        if not active_codes:
            await query.edit_message_text("لا توجد أكواد متاحة حالياً.")
        else:
            message = "الأكواد المتاحة:\n"
            for code, details in active_codes.items():
                message += f"- الكود: {code} (للمجموعة: {details['group_id']})\n"
            await query.edit_message_text(message)

async def get_group_id(update: Update, context: CallbackContext) -> int:
    try:
        group_id = int(update.message.text)
        
        # التحقق من صلاحيات البوت في المجموعة
        if not await check_bot_permissions(context, group_id):
            await update.message.reply_text(
                "البوت لا يملك الصلاحيات الكافية في هذه المجموعة.\n"
                "يجب أن يكون البوت مسؤولاً ولديه الصلاحيات التالية:\n"
                "- يمكنه إضافة أعضاء (can_invite_users)\n"
                "- يمكنه إرسال رسائل (can_send_messages)\n"
                "الرجاء تعديل صلاحيات البوت ثم المحاولة مرة أخرى."
            )
            return ConversationHandler.END
            
        context.user_data['group_id'] = group_id
        await update.message.reply_text("كم عدد الأكواد التي تريد توليدها؟")
        return GET_NUM_CODES
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح لـ ID المجموعة.")
        return GET_GROUP_ID

async def get_num_codes(update: Update, context: CallbackContext) -> int:
    try:
        num_codes = int(update.message.text)
        if num_codes <= 0:
            await update.message.reply_text("الرجاء إدخال عدد أكبر من الصفر.")
            return GET_NUM_CODES
            
        group_id = context.user_data['group_id']
        data = load_data()
        
        for _ in range(num_codes):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            data['codes'][code] = {
                'group_id': group_id,
                'generated_at': datetime.now().isoformat()
            }
        
        save_data(data)
        
        await update.message.reply_text(
            f"تم توليد {num_codes} كود بنجاح للمجموعة {group_id}.\n"
            "يمكنك عرض الأكواد المتاحة باستخدام الأمر /show_codes"
        )
        
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح.")
        return GET_NUM_CODES

async def get_user_code(update: Update, context: CallbackContext) -> int:
    user_code = update.message.text.strip().upper()
    data = load_data()
    
    if user_code in data['used_codes']:
        await update.message.reply_text("هذا الكود تم استخدامه مسبقاً.")
        return GET_USER_CODE
    
    if user_code in data['codes']:
        group_id = data['codes'][user_code]['group_id']
        user = update.effective_user
        
        # التحقق من صلاحيات البوت قبل الإضافة
        if not await check_bot_permissions(context, group_id):
            await update.message.reply_text(
                "عذراً، لا يمكن إضافتك حالياً بسبب مشكلة في صلاحيات البوت.\n"
                "الرجاء إبلاغ المسؤول."
            )
            return GET_USER_CODE
        
        try:
            # إضافة المستخدم إلى المجموعة
            await context.bot.add_chat_member(
                chat_id=group_id,
                user_id=user.id,
            )
            
            # وضع الكود كـ مستخدم
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
            await context.bot.send_message(
                chat_id=group_id,
                text=welcome_message
            )
            
            await update.message.reply_text("تمت إضافتك إلى المجموعة بنجاح!")
            
        except Exception as e:
            logger.error(f"Error adding user to group: {e}")
            await update.message.reply_text("حدث خطأ أثناء محاولة إضافتك إلى المجموعة. الرجاء المحاولة لاحقاً.")
    else:
        await update.message.reply_text("الكود المدخل خاطئ. حاول إدخال الكود بشكل صحيح.")
        return GET_USER_CODE
    
    return ConversationHandler.END

async def show_codes_command(update: Update, context: CallbackContext) -> None:
    data = load_data()
    active_codes = {k: v for k, v in data['codes'].items() if k not in data['used_codes']}
    
    if not active_codes:
        await update.message.reply_text("لا توجد أكواد متاحة حالياً.")
    else:
        message = "الأكواد المتاحة:\n"
        for code, details in active_codes.items():
            message += f"- الكود: {code} (للمجموعة: {details['group_id']})\n"
        await update.message.reply_text(message)

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('تم إلغاء العملية.')
    return ConversationHandler.END

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="حدث خطأ في البوت:", exc_info=context.error)
    if update.effective_message:
        await update.effective_message.reply_text('حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.')

def main() -> None:
    # إنشاء التطبيق وإضافة المعالجات
    application = Application.builder().token(TOKEN).build()

    # معالج المحادثة للمسؤول
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_id)],
            GET_NUM_CODES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_num_codes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # معالج المحادثة للمستخدم العادي
    user_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
        states={
            GET_USER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # إضافة جميع المعالجات
    application.add_handler(admin_conv_handler)
    application.add_handler(user_conv_handler)
    application.add_handler(CommandHandler("show_codes", show_codes_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
