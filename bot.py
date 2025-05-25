#!/usr/bin/env python3 v1.0
import os
import logging
import json
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    PicklePersistence,
)

# تهيئة السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/home/ec2-user/projects/WelMemBot/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# بيانات التكوين
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
GROUP_ID = -1002329495586
ADMIN_ID = 764559466

# حالات المحادثة
GROUP_LINK, NUM_CODES, USER_CODE = range(3)

# مسار ملف البيانات المستدامة
PERSISTENCE_FILE = '/home/ec2-user/projects/WelMemBot/bot_persistence.pickle'

# تحميل البيانات من ملف JSON (للتوافق مع النسخة السابقة)
def load_legacy_data():
    legacy_file = '/home/ec2-user/projects/WelMemBot/bot_data.json'
    if os.path.exists(legacy_file):
        with open(legacy_file, 'r') as f:
            return json.load(f)
    return None

# معالج الأمر /start
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    if user.id == ADMIN_ID:
        update.message.reply_text(
            "مرحبًا يا مسؤول! 👋\n"
            "استخدم /generate لإنشاء أكواد دعوة جديدة.\n"
            "استخدم /stats لعرض إحصائيات الأكواد.\n"
            "استخدم /broadcast لإرسال رسالة لجميع الأعضاء."
        )
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "مرحبًا! 👋\n"
            "أدخل كود الدعوة الخاص بك للانضمام إلى المجموعة."
        )
        return USER_CODE

# بدء عملية إنشاء الأكواد
def generate_codes(update: Update, context: CallbackContext) -> int:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("عفواً، هذا الأمر للمسؤولين فقط.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "أدخل رابط الدعوة للمجموعة:\n"
        "(يجب أن يكون الرابط بصيغة https://t.me/joinchat/xxxxxx)\n"
        "أو /cancel للإلغاء"
    )
    return GROUP_LINK

# معالج رابط الدعوة
def group_link(update: Update, context: CallbackContext) -> int:
    link = update.message.text.strip()
    if not link.startswith('https://t.me/joinchat/'):
        update.message.reply_text("رابط غير صالح! يرجى إدخال رابط دعوة صالح.")
        return GROUP_LINK
    
    context.user_data['invite_link'] = link
    update.message.reply_text("كم عدد أكواد الدعوة التي تريد إنشاءها؟ (1-100)\nأو /cancel للإلغاء")
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
    bot_data = context.bot_data
    
    # إنشاء الأكواد
    codes = []
    for _ in range(num):
        code = generate_unique_code(bot_data.get('codes', {}))
        bot_data.setdefault('codes', {})[code] = {
            'invite_link': invite_link,
            'created_at': datetime.now().isoformat(),
            'used': False,
            'group_id': GROUP_ID
        }
        codes.append(code)
    
    # حفظ البيانات
    context.dispatcher.update_persistence()
    
    # إرسال الأكواد للمسؤول
    update.message.reply_text(
        f"تم إنشاء {num} كود دعوة:\n\n" +
        "\n".join(codes) +
        "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة."
    )
    
    return ConversationHandler.END

# توليد كود فريد
def generate_unique_code(existing_codes, length=8):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if code not in existing_codes:
            return code

# معالج إدخال الكود من قبل المستخدم
def user_code(update: Update, context: CallbackContext) -> int:
    code = update.message.text.upper().strip()
    bot_data = context.bot_data
    user = update.effective_user
    
    if 'used_codes' in bot_data and code in bot_data['used_codes']:
        update.message.reply_text("هذا الكود تم استخدامه مسبقًا.")
        return USER_CODE
    
    if 'codes' not in bot_data or code not in bot_data['codes']:
        update.message.reply_text("Invalid code. Please enter a valid code.", quote=True)
        return USER_CODE
    
    code_info = bot_data['codes'][code]
    
    try:
        # إضافة المستخدم إلى المجموعة
        context.bot.unban_chat_member(
            chat_id=code_info['group_id'],
            user_id=user.id
        )
        
        # إرسال رسالة ترحيبية في المجموعة
        welcome_message = (
            f"أهلاً وسهلاً بك، {user.first_name}!\n\n"
            "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
            "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
        )
        
        context.bot.send_message(
            chat_id=code_info['group_id'],
            text=welcome_message
        )
        
        # تحديث البيانات
        bot_data.setdefault('used_codes', set()).add(code)
        bot_data['codes'][code]['used'] = True
        bot_data['codes'][code]['used_by'] = user.id
        bot_data['codes'][code]['used_at'] = datetime.now().isoformat()
        bot_data.setdefault('users', {})[user.id] = {
            'joined_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
        }
        context.dispatcher.update_persistence()
        
        update.message.reply_text(
            "تمت إضافتك إلى المجموعة بنجاح! 🎉\n"
            "يمكنك الآن الذهاب إلى المجموعة."
        )
        
    except Exception as e:
        logger.error(f"Error adding user to group: {e}", exc_info=True)
        update.message.reply_text(
            "حدث خطأ أثناء محاولة إضافتك إلى المجموعة. يرجى المحاولة لاحقًا."
        )
    
    return ConversationHandler.END

# عرض إحصائيات الأكواد
def stats(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("عفواً، هذا الأمر للمسؤولين فقط.")
        return
    
    bot_data = context.bot_data
    total_codes = len(bot_data.get('codes', {}))
    used_codes = len(bot_data.get('used_codes', set()))
    total_users = len(bot_data.get('users', {}))
    
    update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"• إجمالي الأكواد: {total_codes}\n"
        f"• الأكواد المستخدمة: {used_codes}\n"
        f"• الأكواد المتاحة: {total_codes - used_codes}\n"
        f"• الأعضاء المضافين: {total_users}"
    )

# إرسال رسالة جماعية
def broadcast(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("عفواً، هذا الأمر للمسؤولين فقط.")
        return
    
    if not context.args:
        update.message.reply_text("الاستخدام: /broadcast <الرسالة>")
        return
    
    message = ' '.join(context.args)
    bot_data = context.bot_data
    users = bot_data.get('users', {})
    
    if not users:
        update.message.reply_text("لا يوجد أعضاء لإرسال الرسالة لهم.")
        return
    
    success = 0
    failures = 0
    
    for user_id in users:
        try:
            context.bot.send_message(chat_id=user_id, text=message)
            success += 1
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
            failures += 1
    
    update.message.reply_text(
        f"تم إرسال الرسالة إلى {success} عضو.\n"
        f"فشل الإرسال لـ {failures} عضو."
    )

# إلغاء المحادثة
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# معالج الأخطاء
def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="حدث خطأ في البوت", exc_info=context.error)
    
    if update and update.effective_message:
        update.effective_message.reply_text(
            "عذرًا، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقًا."
        )

# الدالة الرئيسية
def main() -> None:
    # تهيئة استمرارية البيانات
    persistence = PicklePersistence(
        filename=PERSISTENCE_FILE,
        store_chat_data=False,
        store_user_data=False,
        single_file=False
    )
    
    # تحميل البيانات القديمة إذا وجدت
    legacy_data = load_legacy_data()
    if legacy_data:
        persistence.bot_data.update(legacy_data)
        try:
            os.rename('/home/ec2-user/projects/WelMemBot/bot_data.json',
                     '/home/ec2-user/projects/WelMemBot/bot_data.json.backup')
        except Exception as e:
            logger.warning(f"Could not rename legacy data file: {e}")

    # إنشاء Updater مع استمرارية البيانات
    updater = Updater(TOKEN, persistence=persistence, use_context=True)

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
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # تسجيل المعالجات
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('stats', stats))
    dispatcher.add_handler(CommandHandler('broadcast', broadcast, pass_args=True))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(user_code_handler)

    # تسجيل معالج الأخطاء
    dispatcher.add_error_handler(error_handler)

    # بدء البوت
    updater.start_polling(drop_pending_updates=True)
    logger.info("Bot started and running...")
    updater.idle()

if __name__ == '__main__':
    main()
