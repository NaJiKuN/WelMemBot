#!/usr/bin/env python3 v1.1
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

class WelMemBot:
    def __init__(self):
        self.persistence = PicklePersistence(
            filename=PERSISTENCE_FILE,
            store_chat_data=False,
            store_user_data=False,
            single_file=False
        )
        
        self.updater = Updater(TOKEN, persistence=self.persistence, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        self._setup_handlers()
        self._load_legacy_data()

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
        self.dispatcher.add_handler(CommandHandler('broadcast', self.broadcast, pass_args=True))
        self.dispatcher.add_handler(conv_handler)
        self.dispatcher.add_handler(user_code_handler)
        self.dispatcher.add_error_handler(self.error_handler)

    def _load_legacy_data(self):
        legacy_file = '/home/ec2-user/projects/WelMemBot/bot_data.json'
        if os.path.exists(legacy_file):
            try:
                with open(legacy_file, 'r') as f:
                    legacy_data = json.load(f)
                    self.persistence.bot_data.update(legacy_data)
                
                os.rename(legacy_file, f'{legacy_file}.backup')
                logger.info("Migrated legacy data successfully")
            except Exception as e:
                logger.error(f"Failed to migrate legacy data: {e}")

    def start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        if user.id == ADMIN_ID:
            update.message.reply_text(
                "👑 مرحبًا يا مسؤول!\n"
                "🔹 استخدم /generate لإنشاء أكواد دعوة جديدة\n"
                "📊 استخدم /stats لعرض إحصائيات الأكواد\n"
                "📢 استخدم /broadcast لإرسال رسالة لجميع الأعضاء"
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
            "🔗 أرسل رابط الدعوة للمجموعة:\n"
            "(يجب أن يكون الرابط بصيغة https://t.me/joinchat/xxxxxx)\n"
            "أو /cancel للإلغاء"
        )
        return GROUP_LINK

    def group_link(self, update: Update, context: CallbackContext) -> int:
        link = update.message.text.strip()
        if not link.startswith('https://t.me/joinchat/'):
            update.message.reply_text("❌ رابط غير صالح! يرجى إدخال رابط دعوة صالح.")
            return GROUP_LINK
        
        context.user_data['invite_link'] = link
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
        
        invite_link = context.user_data['invite_link']
        bot_data = context.bot_data
        
        codes = []
        for _ in range(num):
            code = self._generate_unique_code(bot_data.get('codes', {}))
            bot_data.setdefault('codes', {})[code] = {
                'invite_link': invite_link,
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
        
        if 'used_codes' in bot_data and code in bot_data['used_codes']:
            update.message.reply_text("❌ هذا الكود تم استخدامه مسبقًا.")
            return USER_CODE
        
        if 'codes' not in bot_data or code not in bot_data['codes']:
            update.message.reply_text("❌ الكود المدخل خاطئ. حاول إدخال الكود بشكل صحيح.")
            return USER_CODE
        
        code_info = bot_data['codes'][code]
        
        try:
            # محاولة إضافة المستخدم إلى المجموعة
            context.bot.unban_chat_member(
                chat_id=code_info['group_id'],
                user_id=user.id
            )
            
            # إرسال رابط الدعوة مباشرة للمستخدم
            context.bot.send_message(
                chat_id=user.id,
                text=f"🎉 تم تفعيل الكود بنجاح!\n"
                     f"انقر على الرابط للانضمام إلى المجموعة:\n"
                     f"{code_info['invite_link']}"
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
                'first_name': user.first_name,
                'username': user.username,
                'joined_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
            }
            context.dispatcher.update_persistence()
            
            update.message.reply_text(
                "✅ تمت إضافتك إلى المجموعة بنجاح!\n"
                "تم إرسال رابط الدعوة إليك في الرسائل الخاصة."
            )
            
        except Exception as e:
            logger.error(f"Error adding user to group: {e}", exc_info=True)
            update.message.reply_text(
                "⚠️ حدث خطأ أثناء محاولة إضافتك إلى المجموعة. يرجى المحاولة لاحقًا.\n"
                "إذا استمرت المشكلة، يرجى التواصل مع المسؤول."
            )
        
        return ConversationHandler.END

    def stats(self, update: Update, context: CallbackContext) -> None:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ عفواً، هذا الأمر للمسؤولين فقط.")
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

    def broadcast(self, update: Update, context: CallbackContext) -> None:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ عفواً، هذا الأمر للمسؤولين فقط.")
            return
        
        if not context.args:
            update.message.reply_text("ℹ️ الاستخدام: /broadcast <الرسالة>")
            return
        
        message = ' '.join(context.args)
        bot_data = context.bot_data
        users = bot_data.get('users', {})
        
        if not users:
            update.message.reply_text("ℹ️ لا يوجد أعضاء لإرسال الرسالة لهم.")
            return
        
        success = 0
        failures = 0
        
        for user_id, user_data in users.items():
            try:
                context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 إشعار من المسؤول:\n\n{message}"
                )
                success += 1
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                failures += 1
        
        update.message.reply_text(
            f"📤 نتائج الإرسال الجماعي:\n"
            f"• تم الإرسال بنجاح: {success}\n"
            f"• فشل في الإرسال: {failures}"
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
        logger.info("Bot started and running...")
        self.updater.idle()

if __name__ == '__main__':
    bot = WelMemBot()
    bot.run()
