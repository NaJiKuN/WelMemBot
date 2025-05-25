#v3.0
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
import os
import random
import string
from datetime import datetime, timedelta

# تهيئة السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# الثوابت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
GROUP_ID = -1002329495586
ADMIN_ID = 764559466
DATA_FILE = '/home/ec2-user/projects/WelMemBot/data.json'

# حالات المحادثة
GROUP_ID_INPUT, NUM_CODES_INPUT = range(2)

class WelMemBot:
    def __init__(self):
        self.load_data()

    def load_data(self):
        """تحميل البيانات من ملف JSON"""
        try:
            with open(DATA_FILE, 'r') as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {
                'group_id': GROUP_ID,
                'codes': {},
                'used_codes': set()
            }
            self.save_data()

    def save_data(self):
        """حفظ البيانات إلى ملف JSON"""
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def generate_code(self, length=8):
        """توليد كود عشوائي"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def start(self, update: Update, context: CallbackContext) -> None:
        """معالجة أمر /start"""
        user_id = update.effective_user.id
        
        if user_id == ADMIN_ID:
            update.message.reply_text(
                "مرحباً يا مسؤول!\n"
                "لإنشاء أكواد دعوة، استخدم الأمر /generate\n"
                "لعرض الأكواد الحالية، استخدم الأمر /list_codes"
            )
        else:
            update.message.reply_text(
                "مرحباً! الرجاء إدخال كود الدعوة الخاص بك للانضمام إلى المجموعة."
            )

    def generate_codes(self, update: Update, context: CallbackContext) -> int:
        """بدء عملية إنشاء الأكواد"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            update.message.reply_text("ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return ConversationHandler.END

        update.message.reply_text(
            "الرجاء إدخال معرف المجموعة (Group ID) التي تريد إنشاء الأكواد لها:\n"
            "مثال: -1002329495586"
        )
        return GROUP_ID_INPUT

    def get_group_id(self, update: Update, context: CallbackContext) -> int:
        """الحصول على معرف المجموعة من المسؤول"""
        try:
            group_id = int(update.message.text)
            context.user_data['group_id'] = group_id
            update.message.reply_text(
                f"تم تعيين معرف المجموعة إلى {group_id}.\n"
                "الرجاء إدخال عدد الأكواد التي تريد إنشاءها:"
            )
            return NUM_CODES_INPUT
        except ValueError:
            update.message.reply_text("معرف المجموعة غير صالح. الرجاء إدخال رقم صحيح.")
            return GROUP_ID_INPUT

    def get_num_codes(self, update: Update, context: CallbackContext) -> int:
        """الحصول على عدد الأكواد من المسؤول وإنشاؤها"""
        try:
            num_codes = int(update.message.text)
            if num_codes <= 0:
                raise ValueError

            group_id = context.user_data['group_id']
            codes = []

            for _ in range(num_codes):
                code = self.generate_code()
                self.data['codes'][code] = {
                    'group_id': group_id,
                    'used': False,
                    'created_at': datetime.now().isoformat()
                }
                codes.append(code)

            self.save_data()

            update.message.reply_text(
                f"تم إنشاء {num_codes} كود للمجموعة {group_id}:\n\n" +
                "\n".join(codes) +
                "\n\nسيتم إبطال كل كود بعد استخدامه مرة واحدة."
            )
            return ConversationHandler.END
        except ValueError:
            update.message.reply_text("الرجاء إدخال رقم صحيح موجب.")
            return NUM_CODES_INPUT

    def list_codes(self, update: Update, context: CallbackContext) -> None:
        """عرض جميع الأكواد الحالية"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            update.message.reply_text("ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return

        if not self.data['codes']:
            update.message.reply_text("لا توجد أكواد حالياً.")
            return

        active_codes = []
        used_codes = []

        for code, details in self.data['codes'].items():
            if details['used']:
                used_codes.append(code)
            else:
                active_codes.append(code)

        message = "الأكواد النشطة:\n"
        message += "\n".join(active_codes) if active_codes else "لا توجد أكواد نشطة.\n"
        message += "\n\nالأكواد المستخدمة:\n"
        message += "\n".join(used_codes) if used_codes else "لا توجد أكواد مستخدمة."

        update.message.reply_text(message)

    def handle_code(self, update: Update, context: CallbackContext) -> None:
        """معالجة كود الدعوة من المستخدم"""
        user = update.effective_user
        code = update.message.text.strip()

        if code in self.data['codes'] and not self.data['codes'][code]['used']:
            # الكود صالح
            group_id = self.data['codes'][code]['group_id']
            self.data['codes'][code]['used'] = True
            self.data['used_codes'].add(code)
            self.save_data()

            try:
                # إضافة المستخدم إلى المجموعة
                context.bot.send_message(
                    chat_id=group_id,
                    text=f"تمت إضافة {user.mention_markdown()} إلى المجموعة باستخدام كود الدعوة."
                )
                
                # إرسال رسالة الترحيب
                welcome_message = (
                    f"أهلاً وسهلاً بك، {user.mention_markdown()}!\n"
                    "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
                    "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
                )
                context.bot.send_message(chat_id=group_id, text=welcome_message, parse_mode='Markdown')

                update.message.reply_text(
                    "تمت إضافتك إلى المجموعة بنجاح! تحقق من رسائل المجموعة للترحيب بك."
                )
            except Exception as e:
                logger.error(f"Error adding user to group: {e}")
                update.message.reply_text(
                    "حدث خطأ أثناء إضافتك إلى المجموعة. الرجاء المحاولة لاحقاً."
                )
        else:
            update.message.reply_text("The entered code is incorrect. Please try entering the code correctly.")

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """إلغاء المحادثة"""
        update.message.reply_text('تم الإلغاء.')
        return ConversationHandler.END

    def error_handler(self, update: Update, context: CallbackContext) -> None:
        """معالجة الأخطاء"""
        logger.error(msg="حدث خطأ في البوت:", exc_info=context.error)
        
        if update.effective_message:
            update.effective_message.reply_text(
                "حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى لاحقاً."
            )

def main() -> None:
    """تشغيل البوت"""
    bot = WelMemBot()
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # معالج الأوامر
    dispatcher.add_handler(CommandHandler("start", bot.start))
    dispatcher.add_handler(CommandHandler("list_codes", bot.list_codes))

    # معالج المحادثة لإنشاء الأكواد
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', bot.generate_codes)],
        states={
            GROUP_ID_INPUT: [MessageHandler(Filters.text & ~Filters.command, bot.get_group_id)],
            NUM_CODES_INPUT: [MessageHandler(Filters.text & ~Filters.command, bot.get_num_codes)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    dispatcher.add_handler(conv_handler)

    # معالج رسائل الأكواد
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, bot.handle_code))

    # معالج الأخطاء
    dispatcher.add_error_handler(bot.error_handler)

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
