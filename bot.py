#!/usr/bin/env python3 v1.2
import os
import logging
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

class WelMemBot:
    def __init__(self):
        self.persistence = PicklePersistence(
            filename='/home/ec2-user/projects/WelMemBot/bot_data.pickle',
            store_chat_data=False,
            store_user_data=False
        )
        
        self.updater = Updater(TOKEN, persistence=self.persistence, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        self._setup_handlers()

    def _setup_handlers(self):
        # معالجات المحادثة للمسؤول
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('generate', self.generate_codes)],
            states={
                GROUP_LINK: [MessageHandler(Filters.text & ~Filters.command, self.group_link)],
                NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, self.num_codes)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        # معالجة إدخال الكود من قبل المستخدم
        user_code_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.text & ~Filters.command, self.user_code)],
            states={
                USER_CODE: [MessageHandler(Filters.text & ~Filters.command, self.user_code)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        # تسجيل المعالجات
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('stats', self.stats))
        self.dispatcher.add_handler(conv_handler)
        self.dispatcher.add_handler(user_code_handler)
        self.dispatcher.add_error_handler(self.error_handler)

    def start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        if user.id == ADMIN_ID:
            update.message.reply_text(
                "👑 مرحبًا يا مسؤول!\n"
                "🔹 استخدم /generate لإنشاء أكواد دعوة جديدة\n"
                "📊 استخدم /stats لعرض إحصائيات الأكواد"
            )
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "👋 مرحبًا!\n"
                "🔑 أدخل كود الدعوة الخاص بك للانضمام إلى المجموعة"
            )
            return USER_CODE

    def generate_codes(self, update: Update, context: CallbackContext) -> int:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ عفواً، هذا الأمر للمسؤولين فقط.")
            return ConversationHandler.END
        
        update.message.reply_text(
            "🔢 كم عدد أكواد الدعوة التي تريد إنشاءها؟ (1-100)\n"
            "أو /cancel للإلغاء"
        )
        return NUM_CODES

    def num_codes(self, update: Update, context: CallbackContext) -> int:
        try:
            num = int(update.message.text)
            if num <= 0 or num > 100:
                update.message.reply_text("⚠️ الرجاء إدخال عدد بين 1 و 100.")
                return NUM_CODES
        except ValueError:
            update.message.reply_text("⚠️ الرجاء إدخال رقم صحيح.")
            return NUM_CODES
        
        bot_data = context.bot_data
        codes = []
        
        for _ in range(num):
            code = self._generate_unique_code(bot_data.get('codes', {}))
            bot_data.setdefault('codes', {})[code] = {
                'created_at': datetime.now().isoformat(),
                'used': False,
                'group_id': GROUP_ID
            }
            codes.append(code)
        
        context.dispatcher.update_persistence()
        
        update.message.reply_text(
            f"✅ تم إنشاء {num} كود دعوة:\n\n" +
            "\n".join([f"• {code}" for code in codes]) +
            "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة."
        )
        
        return ConversationHandler.END

    def _generate_unique_code(self, existing_codes, length=8):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            if code not in existing_codes:
                return code

    def user_code(self, update: Update, context: CallbackContext) -> int:
        code = update.message.text.upper().strip()
        bot_data = context.bot_data
        user = update.effective_user
        
        # التحقق من صحة الكود
        if 'codes' not in bot_data or code not in bot_data['codes']:
            update.message.reply_text("❌ الكود المدخل غير صحيح.")
            return USER_CODE
        
        code_info = bot_data['codes'][code]
        
        # التحقق من استخدام الكود مسبقاً
        if code_info['used']:
            update.message.reply_text("❌ هذا الكود تم استخدامه مسبقًا.")
            return USER_CODE
        
        try:
            # إضافة المستخدم مباشرة إلى المجموعة
            context.bot.unban_chat_member(
                chat_id=GROUP_ID,
                user_id=user.id
            )
            
            # منح المستخدم صلاحيات العضو العادي
            context.bot.restrict_chat_member(
                chat_id=GROUP_ID,
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
            
            # إرسال رسالة ترحيبية في المجموعة
            welcome_message = (
                f"🎉 أهلاً وسهلاً بك، {user.mention_markdown()} في المجموعة!\n\n"
                "🔹 سيتم إنهاء عضويتك بعد شهر تلقائيًا\n"
                "🔹 يُرجى الالتزام بقوانين المجموعة"
            )
            
            context.bot.send_message(
                chat_id=GROUP_ID,
                text=welcome_message,
                parse_mode='Markdown'
            )
            
            # تحديث حالة الكود
            code_info['used'] = True
            code_info['used_by'] = user.id
            code_info['used_at'] = datetime.now().isoformat()
            
            # حفظ بيانات المستخدم
            bot_data.setdefault('users', {})[user.id] = {
                'first_name': user.first_name,
                'username': user.username,
                'joined_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
            }
            
            context.dispatcher.update_persistence()
            
            update.message.reply_text(
                "✅ تمت إضافتك إلى المجموعة بنجاح!\n"
                "يمكنك الآن الذهاب إلى المجموعة."
            )
            
        except Exception as e:
            logger.error(f"خطأ في إضافة المستخدم: {e}", exc_info=True)
            update.message.reply_text(
                "⚠️ حدث خطأ أثناء إضافتك إلى المجموعة. يرجى المحاولة لاحقًا."
            )
        
        return ConversationHandler.END

    def stats(self, update: Update, context: CallbackContext) -> None:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ عفواً، هذا الأمر للمسؤولين فقط.")
            return
        
        bot_data = context.bot_data
        total_codes = len(bot_data.get('codes', {}))
        used_codes = sum(1 for code in bot_data.get('codes', {}).values() if code['used'])
        active_users = len(bot_data.get('users', {}))
        
        update.message.reply_text(
            f"📊 إحصائيات البوت:\n\n"
            f"• إجمالي الأكواد المولدة: {total_codes}\n"
            f"• الأكواد المستخدمة: {used_codes}\n"
            f"• الأكواد المتاحة: {total_codes - used_codes}\n"
            f"• الأعضاء النشطين: {active_users}"
        )

    def cancel(self, update: Update, context: CallbackContext) -> int:
        update.message.reply_text("تم إلغاء العملية.")
        return ConversationHandler.END

    def error_handler(self, update: Update, context: CallbackContext) -> None:
        logger.error(msg="حدث خطأ في البوت", exc_info=context.error)
        
        if update and update.effective_message:
            update.effective_message.reply_text(
                "⚠️ عذرًا، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقًا."
            )

    def run(self):
        self.updater.start_polling(drop_pending_updates=True)
        logger.info("تم تشغيل البوت بنجاح...")
        self.updater.idle()

if __name__ == '__main__':
    bot = WelMemBot()
    bot.run()
