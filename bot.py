#!/usr/bin/env python3 v1.3
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
NUM_CODES, USER_CODE = range(2)

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
                NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, self.create_codes)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        # معالجة إدخال الكود من قبل المستخدم
        user_code_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.text & ~Filters.command, self.handle_user_code)],
            states={
                USER_CODE: [MessageHandler(Filters.text & ~Filters.command, self.handle_user_code)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        # تسجيل المعالجات
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('stats', self.show_stats))
        self.dispatcher.add_handler(conv_handler)
        self.dispatcher.add_handler(user_code_handler)
        self.dispatcher.add_error_handler(self.handle_errors)

    def start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        if user.id == ADMIN_ID:
            update.message.reply_text(
                "👑 **مرحبًا يا مسؤول!**\n\n"
                "🔹 /generate - إنشاء أكواد دعوة جديدة\n"
                "📊 /stats - عرض إحصائيات الأكواد\n\n"
                "يمكنك إنشاء أكواد دعوة للأعضاء الجدد"
            )
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "👋 **مرحبًا بك!**\n\n"
                "🔑 الرجاء إدخال كود الدعوة للانضمام إلى المجموعة"
            )
            return USER_CODE

    def generate_codes(self, update: Update, context: CallbackContext) -> int:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ **عذرًا، هذا الأمر للمسؤولين فقط.**")
            return ConversationHandler.END
        
        update.message.reply_text(
            "🔢 **إنشاء أكواد دعوة جديدة**\n\n"
            "الرجاء إدخال عدد الأكواد المطلوبة (1-100):\n"
            "أو /cancel للإلغاء"
        )
        return NUM_CODES

    def create_codes(self, update: Update, context: CallbackContext) -> int:
        try:
            num = int(update.message.text)
            if not 1 <= num <= 100:
                update.message.reply_text("⚠️ **الرجاء إدخال عدد بين 1 و 100**")
                return NUM_CODES
        except ValueError:
            update.message.reply_text("⚠️ **الرجاء إدخال رقم صحيح**")
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
        
        # إرسال الأكواد للمسؤول في رسالة منسقة
        update.message.reply_text(
            f"✅ **تم إنشاء {num} كود دعوة:**\n\n" +
            "\n".join([f"• `{code}`" for code in codes]) +
            "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    def handle_user_code(self, update: Update, context: CallbackContext) -> int:
        code = update.message.text.upper().strip()
        bot_data = context.bot_data
        user = update.effective_user
        
        # التحقق من وجود الكود في قاعدة البيانات
        if 'codes' not in bot_data or code not in bot_data['codes']:
            update.message.reply_text("❌ **الكود المدخل غير صحيح**")
            return USER_CODE
        
        code_info = bot_data['codes'][code]
        
        # التحقق من استخدام الكود مسبقاً
        if code_info['used']:
            update.message.reply_text("❌ **هذا الكود تم استخدامه مسبقًا**")
            return USER_CODE
        
        try:
            # 1. إضافة المستخدم إلى المجموعة
            self._add_user_to_group(context.bot, user.id)
            
            # 2. تحديث حالة الكود
            self._update_code_status(bot_data, code, user.id)
            
            # 3. إرسال رسالة ترحيبية
            self._send_welcome_messages(context.bot, user)
            
            update.message.reply_text(
                "✅ **تمت إضافتك إلى المجموعة بنجاح!**\n\n"
                "يمكنك الآن زيارة المجموعة والبدء في المشاركة.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"فشل في إضافة المستخدم: {e}", exc_info=True)
            update.message.reply_text(
                "⚠️ **حدث خطأ أثناء الإضافة**\n"
                "الرجاء المحاولة لاحقًا أو التواصل مع المسؤول."
            )
        
        return ConversationHandler.END

    def _add_user_to_group(self, bot, user_id):
        """إضافة المستخدم إلى المجموعة مع الصلاحيات المناسبة"""
        # رفع الحظر أولاً إن وجد
        try:
            bot.unban_chat_member(chat_id=GROUP_ID, user_id=user_id)
        except Exception as e:
            logger.info(f"المستخدم لم يكن محظورًا: {e}")
        
        # منح صلاحيات العضو العادي
        bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=user_id,
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

    def _update_code_status(self, bot_data, code, user_id):
        """تحديث حالة الكود بعد استخدامه"""
        bot_data['codes'][code]['used'] = True
        bot_data['codes'][code]['used_by'] = user_id
        bot_data['codes'][code]['used_at'] = datetime.now().isoformat()
        
        # حفظ بيانات المستخدم
        bot_data.setdefault('users', {})[user_id] = {
            'joined_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
        }

    def _send_welcome_messages(self, bot, user):
        """إرسال رسائل الترحيب للمستخدم وفي المجموعة"""
        # رسالة ترحيبية في المجموعة
        welcome_group = (
            f"🎊 **مرحبًا بكم جميعًا!**\n\n"
            f"انضم عضو جديد إلى مجموعتنا:\n"
            f"👤 {user.mention_markdown()}\n\n"
            f"نتمنى له وقتًا ممتعًا معنا!"
        )
        
        bot.send_message(
            chat_id=GROUP_ID,
            text=welcome_group,
            parse_mode='Markdown'
        )

    def show_stats(self, update: Update, context: CallbackContext) -> None:
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ **عذرًا، هذا الأمر للمسؤولين فقط**")
            return
        
        bot_data = context.bot_data
        total_codes = len(bot_data.get('codes', {}))
        used_codes = sum(1 for c in bot_data.get('codes', {}).values() if c['used'])
        active_users = len(bot_data.get('users', {}))
        
        update.message.reply_text(
            "📈 **إحصائيات البوت:**\n\n"
            f"• الأكواد المولدة: `{total_codes}`\n"
            f"• الأكواد المستخدمة: `{used_codes}`\n"
            f"• الأكواد المتاحة: `{total_codes - used_codes}`\n"
            f"• الأعضاء النشطين: `{active_users}`",
            parse_mode='Markdown'
        )

    def cancel(self, update: Update, context: CallbackContext) -> int:
        update.message.reply_text("تم إلغاء العملية.")
        return ConversationHandler.END

    def handle_errors(self, update: Update, context: CallbackContext) -> None:
        logger.error("حدث خطأ في البوت", exc_info=context.error)
        if update and update.effective_message:
            update.effective_message.reply_text(
                "⚠️ حدث خطأ غير متوقع. الرجاء المحاولة لاحقًا."
            )

    def _generate_unique_code(self, existing_codes, length=8):
        """توليد كود فريد غير مستخدم من قبل"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            if code not in existing_codes:
                return code

    def run(self):
        self.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ تم تشغيل البوت بنجاح")
        self.updater.idle()

if __name__ == '__main__':
    bot = WelMemBot()
    bot.run()
