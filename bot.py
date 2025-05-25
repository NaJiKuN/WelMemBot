# v3.2
import logging
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)
import random
import string
import json
import os

# تهيئة السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الثوابت
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
DATA_FILE = 'codes.json'

# حالات المحادثة
GETTING_GROUP_ID, GETTING_NUM_CODES = range(2)

class WelMemBot:
    def __init__(self):
        self.codes = self.load_data()
        
    def load_data(self):
        """تحميل البيانات من الملف"""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}
    
    def save_data(self):
        """حفظ البيانات في الملف"""
        with open(DATA_FILE, 'w') as f:
            json.dump(self.codes, f, indent=4)
    
    def generate_code(self, length=8):
        """توليد كود عشوائي"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    def start(self, update: Update, context: CallbackContext):
        """معالجة أمر /start"""
        user_id = update.effective_user.id
        if user_id == ADMIN_ID:
            update.message.reply_text(
                "مرحبًا أيها المسؤول!\n"
                "استخدم /generate لإنشاء أكواد دعوة.\n"
                "استخدم /stats لرؤية الإحصائيات."
            )
        else:
            update.message.reply_text(
                "مرحبًا! الرجاء إدخال كود الدعوة الخاص بك للانضمام إلى المجموعة."
            )
    
    def generate_codes_start(self, update: Update, context: CallbackContext):
        """بدء عملية توليد الأكواد"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return ConversationHandler.END
        
        update.message.reply_text(
            "الرجاء إدخال معرف المجموعة (GROUP_ID) التي تريد إنشاء الأكواد لها:\n"
            "مثال: -1002329495586"
        )
        return GETTING_GROUP_ID
    
    def get_group_id(self, update: Update, context: CallbackContext):
        """الحصول على معرف المجموعة"""
        try:
            group_id = int(update.message.text)
            context.user_data['group_id'] = group_id
            update.message.reply_text(
                f"تم تعيين معرف المجموعة إلى {group_id}.\n"
                "الرجاء إدخال عدد الأكواد التي تريد توليدها:"
            )
            return GETTING_NUM_CODES
        except ValueError:
            update.message.reply_text("معرف المجموعة غير صالح. الرجاء إدخال رقم صحيح.")
            return GETTING_GROUP_ID
    
    def get_num_codes(self, update: Update, context: CallbackContext):
        """الحصول على عدد الأكواد وتوليدها"""
        try:
            num_codes = int(update.message.text)
            if num_codes <= 0:
                update.message.reply_text("الرجاء إدخال عدد أكبر من الصفر.")
                return GETTING_NUM_CODES
            
            group_id = context.user_data['group_id']
            generated_codes = []
            
            for _ in range(num_codes):
                code = self.generate_code()
                self.codes[code] = {
                    'group_id': group_id,
                    'used': False,
                    'used_by': None
                }
                generated_codes.append(code)
            
            self.save_data()
            
            update.message.reply_text(
                f"تم توليد {num_codes} أكواد بنجاح:\n\n" +
                "\n".join(generated_codes) +
                "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة."
            )
            
            return ConversationHandler.END
        except ValueError:
            update.message.reply_text("عدد غير صالح. الرجاء إدخال رقم صحيح.")
            return GETTING_NUM_CODES
    
    def cancel(self, update: Update, context: CallbackContext):
        """إلغاء العملية"""
        update.message.reply_text("تم إلغاء العملية.")
        return ConversationHandler.END
    
    def handle_code(self, update: Update, context: CallbackContext):
        """معالجة كود الدعوة من المستخدم"""
        # تجاهل إذا كان المستخدم في محادثة توليد أكواد
        if context.user_data.get('in_conversation', False):
            return
        
        user = update.effective_user
        code = update.message.text.upper()
        
        if code in self.codes:
            if not self.codes[code]['used']:
                group_id = self.codes[code]['group_id']
                
                try:
                    # إضافة المستخدم إلى المجموعة
                    context.bot.add_chat_member(
                        chat_id=group_id,
                        user_id=user.id,
                        can_send_messages=True
                    )
                    
                    # تحديث حالة الكود
                    self.codes[code]['used'] = True
                    self.codes[code]['used_by'] = user.id
                    self.save_data()
                    
                    # إرسال رسالة ترحيبية في المجموعة
                    welcome_message = (
                        f"أهلاً وسهلاً بك، {user.full_name}!\n"
                        "سيتم إنهاء عضويتك بعد شهر تلقائيًا.\n"
                        "يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
                    )
                    context.bot.send_message(
                        chat_id=group_id,
                        text=welcome_message
                    )
                    
                    update.message.reply_text(
                        "تمت إضافتك إلى المجموعة بنجاح! الرجاء التحقق من الرسائل في المجموعة."
                    )
                except Exception as e:
                    logger.error(f"Error adding user to group: {e}")
                    update.message.reply_text(
                        "حدث خطأ أثناء محاولة إضافتك إلى المجموعة. الرجاء المحاولة لاحقًا."
                    )
            else:
                update.message.reply_text("هذا الكود قد تم استخدامه مسبقًا.")
        else:
            update.message.reply_text("الكود المدخل خاطئ. حاول إدخال الكود بشكل صحيح.")
    
    def stats(self, update: Update, context: CallbackContext):
        """عرض إحصائيات الأكواد"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return
        
        total_codes = len(self.codes)
        used_codes = sum(1 for code in self.codes.values() if code['used'])
        unused_codes = total_codes - used_codes
        
        update.message.reply_text(
            f"إحصائيات الأكواد:\n"
            f"- إجمالي الأكواد: {total_codes}\n"
            f"- الأكواد المستخدمة: {used_codes}\n"
            f"- الأكواد المتاحة: {unused_codes}"
        )

def main():
    # إنشاء مثيل من البوت
    bot = WelMemBot()
    
    # إنشاء Updater وتمرير توكن البوت
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # تعريف ConversationHandler أولاً
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', bot.generate_codes_start)],
        states={
            GETTING_GROUP_ID: [
                MessageHandler(Filters.text & ~Filters.command, bot.get_group_id),
                CommandHandler('cancel', bot.cancel)
            ],
            GETTING_NUM_CODES: [
                MessageHandler(Filters.text & ~Filters.command, bot.get_num_codes),
                CommandHandler('cancel', bot.cancel)
            ],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
        per_user=True,
        per_chat=True
    )
    
    # إضافة handlers بالترتيب الصحيح
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("start", bot.start))
    dispatcher.add_handler(CommandHandler("stats", bot.stats))
    
    # إضافة MessageHandler آخر مع فلتر لتجنب التداخل
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command & ~Filters.update.edited_message,
        bot.handle_code
    ))
    
    # بدء البوت
    updater.start_polling()
    logger.info("Bot is running and responding to commands...")
    updater.idle()

if __name__ == '__main__':
    main()
