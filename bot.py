#!/usr/bin/env python3 v1.4
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

class GroupMembersBot:
    def __init__(self):
        # إعداد استمرارية البيانات
        self.persistence = PicklePersistence(
            filename='/home/ec2-user/projects/WelMemBot/bot_data.pickle',
            store_chat_data=False,
            store_user_data=False
        )
        
        # إنشاء وتكوين Updater
        self.updater = Updater(TOKEN, persistence=self.persistence, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        # تسجيل معالجات الأوامر والمحادثات
        self._register_handlers()
        
        # التحقق من صلاحيات البوت عند التشغيل
        self._check_bot_permissions()

    def _register_handlers(self):
        """تسجيل جميع معالجات الأوامر والمحادثات"""
        # معالج إنشاء الأكواد
        code_generation_handler = ConversationHandler(
            entry_points=[CommandHandler('generate', self.start_code_generation)],
            states={
                NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, self.generate_codes)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_operation)],
        )

        # معالج إدخال الكود من المستخدم
        code_usage_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.text & ~Filters.command, self.process_user_code)],
            states={
                USER_CODE: [MessageHandler(Filters.text & ~Filters.command, self.process_user_code)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_operation)],
        )

        # تسجيل المعالجات
        self.dispatcher.add_handler(CommandHandler('start', self.welcome_message))
        self.dispatcher.add_handler(CommandHandler('stats', self.display_statistics))
        self.dispatcher.add_handler(code_generation_handler)
        self.dispatcher.add_handler(code_usage_handler)
        self.dispatcher.add_error_handler(self.handle_errors)

    def _check_bot_permissions(self):
        """التحقق من صلاحيات البوت عند التشغيل"""
        try:
            bot = self.updater.bot
            chat_member = bot.get_chat_member(chat_id=GROUP_ID, user_id=bot.id)
            
            if chat_member.status != 'administrator':
                logger.error("البوت ليس مديراً في المجموعة!")
                raise Exception("البوت يحتاج إلى صلاحيات المدير")
                
            if not chat_member.can_invite_users:
                logger.error("البوت لا يملك صلاحية إضافة أعضاء!")
                raise Exception("البوت يحتاج إلى صلاحية إضافة أعضاء")
                
            logger.info("تم التحقق من صلاحيات البوت بنجاح")
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من الصلاحيات: {e}")
            raise

    def welcome_message(self, update: Update, context: CallbackContext) -> int:
        """رسالة الترحيب الأولية"""
        user = update.effective_user
        
        if user.id == ADMIN_ID:
            update.message.reply_text(
                "👑 **مرحبًا يا مسؤول!**\n\n"
                "🔹 /generate - إنشاء أكواد دعوة جديدة\n"
                "📊 /stats - عرض إحصائيات الأكواد\n\n"
                "يمكنك إنشاء أكواد دعوة للأعضاء الجدد",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                "👋 **مرحبًا بك!**\n\n"
                "🔑 الرجاء إدخال كود الدعوة للانضمام إلى المجموعة",
                parse_mode='Markdown'
            )
            return USER_CODE
            
        return ConversationHandler.END

    def start_code_generation(self, update: Update, context: CallbackContext) -> int:
        """بدء عملية إنشاء الأكواد"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text(
                "⛔ **عذرًا، هذا الأمر للمسؤولين فقط**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        update.message.reply_text(
            "🔢 **إنشاء أكواد دعوة جديدة**\n\n"
            "الرجاء إدخال عدد الأكواد المطلوبة (1-100):\n"
            "أو /cancel للإلغاء",
            parse_mode='Markdown'
        )
        return NUM_CODES

    def generate_codes(self, update: Update, context: CallbackContext) -> int:
        """إنشاء أكواد الدعوة"""
        try:
            num_codes = int(update.message.text)
            if not 1 <= num_codes <= 100:
                raise ValueError
        except ValueError:
            update.message.reply_text(
                "⚠️ **الرجاء إدخال عدد صحيح بين 1 و 100**",
                parse_mode='Markdown'
            )
            return NUM_CODES
        
        bot_data = context.bot_data
        bot_data.setdefault('codes', {})
        
        generated_codes = []
        for _ in range(num_codes):
            code = self._create_unique_code(bot_data['codes'])
            bot_data['codes'][code] = {
                'created_at': datetime.now().isoformat(),
                'used': False,
                'group_id': GROUP_ID
            }
            generated_codes.append(code)
        
        context.dispatcher.update_persistence()
        
        update.message.reply_text(
            f"✅ **تم إنشاء {num_codes} كود دعوة:**\n\n" +
            "\n".join([f"• `{code}`" for code in generated_codes]) +
            "\n\nيمكن للمستخدمين استخدام هذه الأكواد للانضمام إلى المجموعة.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    def process_user_code(self, update: Update, context: CallbackContext) -> int:
        """معالجة كود الدعوة من المستخدم"""
        user = update.effective_user
        code = update.message.text.upper().strip()
        bot_data = context.bot_data
        
        # التحقق من صحة الكود
        if 'codes' not in bot_data or code not in bot_data['codes']:
            update.message.reply_text(
                "❌ **الكود المدخل غير صحيح**",
                parse_mode='Markdown'
            )
            return USER_CODE
        
        code_info = bot_data['codes'][code]
        
        # التحقق من استخدام الكود مسبقاً
        if code_info['used']:
            update.message.reply_text(
                "❌ **هذا الكود تم استخدامه مسبقًا**",
                parse_mode='Markdown'
            )
            return USER_CODE
        
        try:
            # إضافة المستخدم إلى المجموعة
            self._add_user_to_group(context.bot, user.id)
            
            # تحديث حالة الكود
            self._mark_code_as_used(bot_data, code, user.id)
            
            # إرسال رسائل الترحيب
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
                "الرجاء المحاولة لاحقًا أو التواصل مع المسؤول.",
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END

    def _add_user_to_group(self, bot, user_id):
        """إضافة المستخدم إلى المجموعة مع الصلاحيات المناسبة"""
        try:
            # رفع الحظر أولاً إن وجد
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

    def _mark_code_as_used(self, bot_data, code, user_id):
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
        welcome_msg = (
            f"🎊 **مرحبًا بكم جميعًا!**\n\n"
            f"انضم عضو جديد إلى مجموعتنا:\n"
            f"👤 {user.mention_markdown()}\n\n"
            f"نتمنى له وقتًا ممتعًا معنا!"
        )
        
        bot.send_message(
            chat_id=GROUP_ID,
            text=welcome_msg,
            parse_mode='Markdown'
        )

    def display_statistics(self, update: Update, context: CallbackContext) -> None:
        """عرض إحصائيات البوت"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text(
                "⛔ **عذرًا، هذا الأمر للمسؤولين فقط**",
                parse_mode='Markdown'
            )
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

    def cancel_operation(self, update: Update, context: CallbackContext) -> int:
        """إلغاء العملية الحالية"""
        update.message.reply_text("تم إلغاء العملية.")
        return ConversationHandler.END

    def handle_errors(self, update: Update, context: CallbackContext) -> None:
        """معالجة الأخطاء العامة"""
        logger.error("حدث خطأ في البوت", exc_info=context.error)
        if update and update.effective_message:
            update.effective_message.reply_text(
                "⚠️ حدث خطأ غير متوقع. الرجاء المحاولة لاحقًا."
            )

    def _create_unique_code(self, existing_codes, length=8):
        """توليد كود فريد غير مستخدم من قبل"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            if code not in existing_codes:
                return code

    def run(self):
        """تشغيل البوت"""
        self.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ تم تشغيل البوت بنجاح")
        self.updater.idle()

if __name__ == '__main__':
    try:
        bot = GroupMembersBot()
        bot.run()
    except Exception as e:
        logger.critical(f"فشل في تشغيل البوت: {e}")
        raise
