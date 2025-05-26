# G1.3

import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import uuid # لتوليد أكواد فريدة
from datetime import datetime, timedelta # لإدارة صلاحية العضوية (اختياري)
import os # لإدارة مسار الملفات

# 1. إعدادات البوت واللوج
# تهيئة نظام التسجيل (logging) لتتبع ما يحدث في البوت
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات البوت كما تم توفيرها
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466 # معرف المشرف (المسؤول)

# مسار مجلد البوت على AWS EC2
BOT_DIR = "/home/ec2-user/projects/WelMemBot"
# التأكد من وجود مجلد البوت، وإن لم يكن موجودًا فسيتم إنشاؤه
os.makedirs(BOT_DIR, exist_ok=True)

# ملف لحفظ الأكواد المولدة. سيتم حفظه في نفس مسار البوت
CODES_FILE = os.path.join(BOT_DIR, "codes.txt")

# قاموس لتخزين الأكواد المولدة. المفتاح هو الكود، والقيمة هي معرف المجموعة (GROUP_ID)
# مثال: {'abcde123': '-1002329495586', 'fghij456': '-1001234567890'}
generated_codes = {}

# تحميل الأكواد الموجودة من الملف عند بدء تشغيل البوت
def load_codes():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, 'r') as f:
            for line in f:
                if ':' in line:
                    code, group_id = line.strip().split(':', 1)
                    generated_codes[code] = group_id
        logger.info(f"تم تحميل {len(generated_codes)} كود من ملف الأكواد.")
    else:
        logger.info("ملف الأكواد غير موجود. سيتم إنشاء ملف جديد عند أول توليد.")

# حفظ الأكواد في الملف
def save_codes():
    with open(CODES_FILE, 'w') as f:
        for code, group_id in generated_codes.items():
            f.write(f"{code}:{group_id}\n")
    logger.info(f"تم حفظ {len(generated_codes)} كود في ملف الأكواد.")

# 2. وظائف الأوامر (Command Handlers)

# دالة بدء البوت /start
def start(update: Update, context):
    user = update.effective_user
    logger.info(f"المستخدم {user.id} بدأ البوت.")
    # التحقق مما إذا كان المستخدم هو المسؤول (Admin)
    if user.id == ADMIN_ID:
        update.message.reply_text(
            f"مرحباً بك يا مشرف! 👋\n"
            "يمكنك استخدام الأوامر التالية:\n"
            "/generate_codes - لتوليد أكواد دعوة جديدة.\n"
            "**ملاحظة:** سيتم حفظ الأكواد في ملف `codes.txt` تلقائياً.\n\n"
            "**للمستخدمين العاديين:**\n"
            "أدخل الكود الذي حصلت عليه للانضمام إلى المجموعة."
        )
    else:
        update.message.reply_text(
            f"مرحباً بك يا {user.first_name}! 👋\n"
            "يرجى إدخال كود الدعوة للانضمام إلى المجموعة الخاصة."
        )

# دالة لتوليد الأكواد /generate_codes (خاصة بالمسؤول)
def generate_codes_command(update: Update, context):
    user = update.effective_user
    # التأكد من أن المستخدم الذي يصدر الأمر هو المسؤول
    if user.id != ADMIN_ID:
        update.message.reply_text("عذراً، هذا الأمر مخصص للمشرفين فقط.")
        return

    logger.info(f"المشرف {user.id} طلب توليد أكواد.")
    # توجيه المشرف لإدخال ID المجموعة وعدد الأكواد
    update.message.reply_text(
        "من فضلك، أرسل لي معرف المجموعة (Group ID) وعدد الأكواد التي ترغب في توليدها.\n"
        "مثال: `-1002329495586 5` (لتوليد 5 أكواد للمجموعة ذات المعرف -1002329495586)."
    )
    # تعيين حالة للمحادثة لتوقع الرد التالي من المشرف
    context.user_data['awaiting_group_id_and_count'] = True

# دالة لمعالجة رسائل النص العادي (لإدخال الأكواد أو إدخال ID المجموعة وعدد الأكواد)
def handle_message(update: Update, context):
    user = update.effective_user
    text = update.message.text

    # حالة: المشرف ينتظر إدخال ID المجموعة وعدد الأكواد
    if user.id == ADMIN_ID and context.user_data.get('awaiting_group_id_and_count'):
        try:
            parts = text.split()
            if len(parts) == 2:
                group_id = parts[0]
                num_codes = int(parts[1])

                if not group_id.startswith('-100'):
                    update.message.reply_text("معرف المجموعة يجب أن يبدأ بـ '-100'. يرجى التأكد من صحة المعرف.")
                    return
                if num_codes <= 0:
                    update.message.reply_text("عدد الأكواد يجب أن يكون أكبر من صفر.")
                    return

                new_codes_output = "الأكواد المولدة:\n"
                for _ in range(num_codes):
                    # توليد كود فريد باستخدام uuid4 وتحويله إلى string واختصار 8 أحرف
                    code = str(uuid.uuid4())[:8]
                    # التأكد من أن الكود فريد قبل إضافته
                    while code in generated_codes:
                        code = str(uuid.uuid4())[:8]
                    generated_codes[code] = group_id
                    new_codes_output += f"• `{code}` (للمجموعة {group_id})\n"
                
                save_codes() # حفظ الأكواد الجديدة
                update.message.reply_text(new_codes_output, parse_mode='Markdown')
                logger.info(f"المشرف {user.id} ولّد {num_codes} كود للمجموعة {group_id}.")
                del context.user_data['awaiting_group_id_and_count'] # مسح الحالة
            else:
                update.message.reply_text("صيغة غير صحيحة. يرجى إدخال معرف المجموعة وعدد الأكواد مفصولين بمسافة. مثال: `-1002329495586 5`")
        except ValueError:
            update.message.reply_text("صيغة غير صحيحة. يرجى التأكد من أن عدد الأكواد رقم صحيح. مثال: `-1002329495586 5`")
        return

    # حالة: المستخدم العادي يدخل كود الدعوة
    entered_code = text.strip()
    logger.info(f"المستخدم {user.id} أدخل الكود: {entered_code}")

    if entered_code in generated_codes:
        target_group_id = generated_codes[entered_code]
        try:
            # محاولة إضافة المستخدم إلى المجموعة
            # يتطلب البوت صلاحية "إضافة أعضاء" في المجموعة المستهدفة
            bot = context.bot
            bot.unban_chat_member(chat_id=target_group_id, user_id=user.id)
            
            # رسالة نجاح للمستخدم
            update.message.reply_text(
                "تمت إضافتك إلى المجموعة بنجاح! 🎉"
            )
            logger.info(f"تمت إضافة المستخدم {user.first_name} ({user.id}) إلى المجموعة {target_group_id} بنجاح.")

            # رسالة ترحيب في المجموعة
            # رسالة الترحيب: "أهلاً وسهلاً بك، {اسم المستخدم}! سيتم إنهاء عضويتك بعد شهر تلقائيًا. يُرجى الالتزام بآداب المجموعة وتجنب المغادرة قبل المدة المحددة، لتجنب إيقاف العضوية."
            welcome_message = (
                f"Welcome, {user.first_name}!\n"
                "Your membership will automatically end after one month.\n"
                "Please adhere to the group's etiquette and avoid leaving before the specified period to prevent membership termination."
            )
            bot.send_message(chat_id=target_group_id, text=welcome_message)
            logger.info(f"تم إرسال رسالة ترحيب للمستخدم {user.first_name} في المجموعة {target_group_id}.")

            # حذف الكود بعد استخدامه ليكون صالحًا لمرة واحدة
            del generated_codes[entered_code]
            save_codes() # حفظ التغييرات في ملف الأكواد
            logger.info(f"تم حذف الكود {entered_code} بعد الاستخدام.")

        except Exception as e:
            logger.error(f"حدث خطأ أثناء إضافة المستخدم {user.id} إلى المجموعة {target_group_id}: {e}")
            update.message.reply_text(
                "عذراً، لم أتمكن من إضافتك إلى المجموعة. قد أكون لا أملك الصلاحيات الكافية، أو أنك محظور من المجموعة. يرجى التواصل مع المسؤول."
            )
    else:
        # رسالة الخطأ إذا كان الكود غير صحيح
        update.message.reply_text("The entered code is incorrect. Please try to enter the code correctly.")
        logger.warning(f"المستخدم {user.id} أدخل كودًا خاطئًا: {entered_code}")

# دالة لمعالجة الأخطاء
def error(update: Update, context):
    logger.warning(f"تحديث '{update}' سبب الخطأ '{context.error}'")

# 3. دالة main لتشغيل البوت
def main():
    # تحميل الأكواد عند بدء تشغيل البوت
    load_codes()

    # إنشاء Updater وتمرير التوكن الخاص بالبوت
    updater = Updater(TOKEN, use_context=True)

    # الحصول على dispatcher لتسجيل المعالجات
    dp = updater.dispatcher

    # تسجيل معالجات الأوامر
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("generate_codes", generate_codes_command))

    # تسجيل معالج الرسائل النصية
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # تسجيل معالج الأخطاء
    dp.add_handler(dp.add_error_handler(error))

    # بدء تشغيل البوت
    updater.start_polling()

    # إبقاء البوت قيد التشغيل حتى يتم الضغط على Ctrl+C
    updater.idle()

if __name__ == '__main__':
    main()
