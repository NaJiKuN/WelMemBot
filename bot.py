# v2.1
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)
import json
import os
from datetime import datetime, timedelta

# تكوين السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# البيانات الثابتة
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
GROUP_ID = -1002329495586
ADMIN_ID = 764559466
DATA_FILE = '/home/ec2-user/projects/WelMemBot/data.json'

# حالات المحادثة
GET_GROUP_ID, GET_NUM_CODES, GET_CODE = range(3)

class WelMemBot:
    def __init__(self):
        self.data = self.load_data()
        
    def load_data(self):
        """تحميل البيانات من ملف JSON"""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {
            'group_id': GROUP_ID,
            'codes': {},
            'used_codes': set()
        }
    
    def save_data(self):
        """حفظ البيانات إلى ملف JSON"""
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def start(self, update: Update, context: CallbackContext) -> None:
        """معالجة أمر /start"""
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
            return GET_CODE
    
    def generate_codes(self, update: Update, context: CallbackContext) -> int:
        """بدء عملية إنشاء الأكواد"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⚠️ ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return ConversationHandler.END
        
        update.message.reply_text(
            "أدخل معرف المجموعة (Group ID) التي تريد إنشاء الأكواد لها:\n"
            "(استخدم -100xxxxxxxxxx)\n"
            "أو اضغط /cancel للإلغاء."
        )
        return GET_GROUP_ID
    
    def get_group_id(self, update: Update, context: CallbackContext) -> int:
        """الحصول على معرف المجموعة من المسؤول"""
        try:
            group_id = int(update.message.text)
            context.user_data['group_id'] = group_id
            update.message.reply_text(
                f"تم تعيين معرف المجموعة إلى: {group_id}\n"
                "كم عدد الأكواد التي تريد إنشاءها؟\n"
                "(أدخل رقمًا بين 1 و 100)\n"
                "أو اضغط /cancel للإلغاء."
            )
            return GET_NUM_CODES
        except ValueError:
            update.message.reply_text("⚠️ معرف المجموعة غير صحيح. يجب أن يكون رقمًا. حاول مرة أخرى.")
            return GET_GROUP_ID
    
    def get_num_codes(self, update: Update, context: CallbackContext) -> int:
        """الحصول على عدد الأكواد المطلوبة من المسؤول"""
        try:
            num_codes = int(update.message.text)
            if 1 <= num_codes <= 100:
                group_id = context.user_data['group_id']
                codes = self._generate_codes(num_codes, group_id)
                
                # حفظ الأكواد
                for code in codes:
                    self.data['codes'][code] = {
                        'group_id': group_id,
                        'used': False,
                        'created_at': datetime.now().isoformat()
                    }
                self.save_data()
                
                # إرسال الأكواد للمسؤول
                update.message.reply_text(
                    f"تم إنشاء {num_codes} كود دعوة للمجموعة {group_id}:\n\n" +
                    "\n".join(codes) +
                    "\n\nسيتمكن المستخدمون من استخدام هذه الأكواد لمرة واحدة للانضمام إلى المجموعة."
                )
                return ConversationHandler.END
            else:
                update.message.reply_text("⚠️ الرقم يجب أن يكون بين 1 و 100. حاول مرة أخرى.")
                return GET_NUM_CODES
        except ValueError:
            update.message.reply_text("⚠️ يجب إدخال رقم صحيح. حاول مرة أخرى.")
            return GET_NUM_CODES
    
    def _generate_codes(self, num_codes: int, group_id: int) -> list:
        """توليد أكواد فريدة"""
        import secrets
        import string
        
        codes = set()
        while len(codes) < num_codes:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if code not in self.data['codes'] and code not in self.data['used_codes']:
                codes.add(code)
        
        return list(codes)
    
    def get_code_from_user(self, update: Update, context: CallbackContext) -> int:
        """الحصول على كود الدعوة من المستخدم"""
        code = update.message.text.upper().strip()
        
        if code in self.data['codes'] and not self.data['codes'][code]['used']:
            # الكود صحيح ولم يتم استخدامه
            group_id = self.data['codes'][code]['group_id']
            user = update.effective_user
            
            try:
                # إضافة المستخدم إلى المجموعة
                context.bot.send_message(
                    chat_id=group_id,
                    text=f"تمت إضافة المستخدم {user.id} إلى المجموعة."
                )
                
                # تحديث حالة الكود
                self.data['codes'][code]['used'] = True
                self.data['codes'][code]['used_by'] = user.id
                self.data['codes'][code]['used_at'] = datetime.now().isoformat()
                self.data['used_codes'].add(code)
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
                
                # إرسال رسالة تأكيد للمستخدم
                update.message.reply_text(
                    "🎉 تمت إضافتك إلى المجموعة بنجاح!\n"
                    "ستجد رسالة ترحيبية بك في المجموعة."
                )
                
            except Exception as e:
                logger.error(f"فشل في إضافة المستخدم إلى المجموعة: {e}")
                update.message.reply_text(
                    "⚠️ حدث خطأ أثناء محاولة إضافتك إلى المجموعة. يرجى المحاولة لاحقًا."
                )
            
            return ConversationHandler.END
        
        else:
            # الكود غير صحيح أو مستخدم
            update.message.reply_text(
                "The entered code is incorrect. Try entering the code correctly."
            )
            return GET_CODE
    
    def stats(self, update: Update, context: CallbackContext) -> None:
        """عرض إحصائيات الأكواد"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⚠️ ليس لديك صلاحية الوصول إلى هذا الأمر.")
            return
        
        total_codes = len(self.data['codes'])
        used_codes = sum(1 for code in self.data['codes'].values() if code['used'])
        available_codes = total_codes - used_codes
        
        update.message.reply_text(
            f"📊 إحصائيات الأكواد:\n"
            f"• إجمالي الأكواد: {total_codes}\n"
            f"• الأكواد المستخدمة: {used_codes}\n"
            f"• الأكواد المتاحة: {available_codes}"
        )
    
    def cancel(self, update: Update, context: CallbackContext) -> int:
        """إلغاء المحادثة الحالية"""
        update.message.reply_text("تم الإلغاء.")
        return ConversationHandler.END

def main() -> None:
    """تشغيل البوت"""
    bot = WelMemBot()
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # معالج الأوامر الأساسية
    dispatcher.add_handler(CommandHandler("start", bot.start))
    dispatcher.add_handler(CommandHandler("stats", bot.stats))

    # معالج إنشاء الأكواد
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', bot.generate_codes)],
        states={
            GET_GROUP_ID: [MessageHandler(Filters.text & ~Filters.command, bot.get_group_id)],
            GET_NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, bot.get_num_codes)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    dispatcher.add_handler(conv_handler)

    # معالج إدخال الأكواد من المستخدمين
    code_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, bot.get_code_from_user)],
        states={
            GET_CODE: [MessageHandler(Filters.text & ~Filters.command, bot.get_code_from_user)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    dispatcher.add_handler(code_handler)

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
