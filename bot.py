# g1.0
import logging
import uuid
from telegram import Update, User, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import Application, CommandHandler, MessageHandler, Filters, CallbackContext, ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

# --- إعدادات أساسية ---
TOKEN = "8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0"
ADMIN_ID = 764559466 # معرف حساب الأدمن الرئيسي

# --- هياكل البيانات لتخزين المعلومات (في الذاكرة) ---
# registered_groups: مجموعة لتخزين معرفات المجموعات التي أضافها الأدمن
# {group_id_str}
registered_groups = set()

# generated_codes: قاموس لتخزين الأكواد التي تم إنشاؤها وربطها بالمجموعة
# { "CODE123": group_id_str }
generated_codes = {}

# used_codes: مجموعة لتخزين الأكواد التي تم استخدامها
# { "CODE123" }
used_codes = set()

# --- إعداد تسجيل الأخطاء ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- وظائف مساعدة ---
def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم هو الأدمن الرئيسي للبوت."""
    return user_id == ADMIN_ID

async def get_user_mention(user: User) -> str:
    """الحصول على ذكر للمستخدم (اسم المستخدم أو الاسم الأول)."""
    if user.username:
        return f"@{user.username}"
    else:
        return user.first_name

# --- أوامر الأدمن ---
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة البدء للأدمن."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("أنت غير مصرح لك باستخدام أوامر الإدارة.")
        return

    await update.message.reply_text(
        "أهلاً بك أيها المدير!\n\n"
        "الأوامر المتاحة:\n"
        "/addgroup GROUP_ID - لإضافة مجموعة جديدة يمكن توليد أكواد لها.\n"
        "  مثال: /addgroup -1001234567890\n"
        "/generatemembershipcodes GROUP_ID COUNT - لتوليد أكواد عضوية لمجموعة معينة.\n"
        "  مثال: /generatemembershipcodes -1001234567890 10\n"
        "/listgroups - لعرض المجموعات المسجلة.\n"
        "/listcodes GROUP_ID - لعرض الأكواد المولدة لمجموعة (الغير مستخدمة).\n"
    )

async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر لإضافة مجموعة جديدة يمكن للبوت إدارة أكوادها."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذا الأمر مخصص للأدمن فقط.")
        return

    try:
        group_id_str = context.args[0]
        if not group_id_str.startswith('-') or not group_id_str[1:].isdigit():
            await update.message.reply_text("معرف المجموعة غير صالح. يجب أن يبدأ بـ '-' ويحتوي على أرقام فقط بعد ذلك.")
            return
        
        # التحقق من أن البوت أدمن في المجموعة المستهدفة
        try:
            chat_admins = await context.bot.get_chat_administrators(chat_id=group_id_str)
            bot_is_admin_in_group = any(admin.user.id == context.bot.id for admin in chat_admins)
            if not bot_is_admin_in_group:
                 await update.message.reply_text(f"البوت ليس مسؤولاً في المجموعة {group_id_str}. يرجى ترقيته إلى مسؤول مع صلاحية 'إضافة أعضاء' و 'إرسال رسائل'.")
                 return
        except (BadRequest, Forbidden) as e:
            await update.message.reply_text(f"لا يمكن الوصول إلى المجموعة {group_id_str} أو الحصول على قائمة المسؤولين. تأكد من صحة المعرف وأن البوت عضو فيها. الخطأ: {e}")
            return


        registered_groups.add(group_id_str)
        await update.message.reply_text(f"تمت إضافة المجموعة ذات المعرف {group_id_str} بنجاح. يمكنك الآن توليد أكواد لها.")
        logger.info(f"Admin {user.id} added group {group_id_str}")

    except (IndexError, ValueError):
        await update.message.reply_text("الاستخدام: /addgroup GROUP_ID\nمثال: /addgroup -1001234567890")
    except Exception as e:
        logger.error(f"Error in add_group_command: {e}")
        await update.message.reply_text("حدث خطأ أثناء إضافة المجموعة.")


async def generate_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر لتوليد أكواد عضوية لمجموعة معينة."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذا الأمر مخصص للأدمن فقط.")
        return

    try:
        group_id_str = context.args[0]
        count = int(context.args[1])

        if group_id_str not in registered_groups:
            await update.message.reply_text(f"المجموعة {group_id_str} ليست مسجلة. يرجى إضافتها أولاً باستخدام /addgroup.")
            return

        if count <= 0 or count > 100: # حد أقصى لعدد الأكواد دفعة واحدة
            await update.message.reply_text("عدد الأكواد يجب أن يكون بين 1 و 100.")
            return

        newly_generated_codes = []
        for _ in range(count):
            # توليد كود فريد (مثلاً 8 أحرف كبيرة وأرقام)
            code = str(uuid.uuid4().hex.upper()[:8])
            while code in generated_codes or code in used_codes: # ضمان التفرد
                 code = str(uuid.uuid4().hex.upper()[:8])
            
            generated_codes[code] = group_id_str
            newly_generated_codes.append(code)
        
        if newly_generated_codes:
            codes_message = "تم توليد الأكواد التالية بنجاح للمجموعة " + group_id_str + ":\n" + "\n".join(newly_generated_codes)
            # إرسال الأكواد في رسائل متعددة إذا كانت طويلة جداً
            for i in range(0, len(codes_message), 4096): # 4096 هو الحد الأقصى لطول الرسالة
                await update.message.reply_text(codes_message[i:i+4096])
            logger.info(f"Admin {user.id} generated {count} codes for group {group_id_str}")
        else:
            await update.message.reply_text("لم يتم توليد أي أكواد جديدة (قد تكون هناك مشكلة).")


    except (IndexError, ValueError):
        await update.message.reply_text("الاستخدام: /generatemembershipcodes GROUP_ID COUNT\nمثال: /generatemembershipcodes -1001234567890 10")
    except Exception as e:
        logger.error(f"Error in generate_codes_command: {e}")
        await update.message.reply_text("حدث خطأ أثناء توليد الأكواد.")

async def list_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لعرض المجموعات المسجلة."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذا الأمر مخصص للأدمن فقط.")
        return
    
    if not registered_groups:
        await update.message.reply_text("لا توجد مجموعات مسجلة حالياً.")
        return
    
    groups_list = "\n".join(list(registered_groups))
    await update.message.reply_text(f"المجموعات المسجلة:\n{groups_list}")

async def list_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لعرض الأكواد المولدة لمجموعة (الغير مستخدمة)."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذا الأمر مخصص للأدمن فقط.")
        return

    try:
        target_group_id = context.args[0]
        if target_group_id not in registered_groups:
            await update.message.reply_text(f"المجموعة {target_group_id} ليست مسجلة.")
            return

        active_codes_for_group = [code for code, group_id in generated_codes.items() 
                                  if group_id == target_group_id and code not in used_codes]

        if not active_codes_for_group:
            await update.message.reply_text(f"لا توجد أكواد فعالة حالياً للمجموعة {target_group_id}.")
            return

        codes_message = f"الأكواد الفعالة للمجموعة {target_group_id}:\n" + "\n".join(active_codes_for_group)
        for i in range(0, len(codes_message), 4096):
            await update.message.reply_text(codes_message[i:i+4096])

    except IndexError:
        await update.message.reply_text("الاستخدام: /listcodes GROUP_ID")
    except Exception as e:
        logger.error(f"Error in list_codes_command: {e}")
        await update.message.reply_text("حدث خطأ أثناء عرض الأكواد.")


# --- أوامر المستخدمين العاديين ومعالجة الأكواد ---
async def start_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة البدء للمستخدم العادي."""
    await update.message.reply_text(
        "أهلاً بك! الرجاء إدخال كود العضوية الخاص بك للإنضمام إلى المجموعة."
    )

async def handle_code_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الرسائل التي قد تحتوي على كود عضوية."""
    user_code = update.message.text.strip().upper()
    user = update.effective_user

    if user_code in used_codes:
        await update.message.reply_text("هذا الكود تم استخدامه مسبقاً.")
        return

    if user_code in generated_codes:
        target_group_id_str = generated_codes[user_code]
        target_group_id = int(target_group_id_str) # تحويل إلى int للاستخدام مع API

        try:
            # محاولة إضافة المستخدم إلى المجموعة (باستخدام unban_chat_member كطريقة لإضافة)
            # هذه الطريقة تتطلب أن يكون البوت أدمن في المجموعة ولديه صلاحية "Ban users"
            # إذا كان المستخدم ليس محظوراً، فإن only_if_banned=False قد تضيفه.
            await context.bot.unban_chat_member(chat_id=target_group_id, user_id=user.id, only_if_banned=False)
            logger.info(f"User {user.id} ({await get_user_mention(user)}) successfully added to group {target_group_id} using code {user_code}.")

            # إرسال رسالة ترحيب في المجموعة
            user_mention_html = user.mention_html() # استخدام HTML لذكر المستخدم بشكل صحيح
            welcome_message = (
                f"Welcome, {user_mention_html}!\n"
                "Your membership will automatically expire after one month.\n"
                "Please adhere to the group's etiquette and avoid leaving before the specified period to prevent membership suspension."
            )
            try:
                await context.bot.send_message(chat_id=target_group_id, text=welcome_message, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Failed to send welcome message to group {target_group_id} for user {user.id}. Error: {e}")
                await update.message.reply_text(f"تمت إضافتك للمجموعة، ولكن حدث خطأ أثناء إرسال رسالة الترحيب في المجموعة. ({e})")


            # وضع علامة على الكود بأنه مستخدم
            used_codes.add(user_code)
            # يمكن إزالة الكود من generated_codes إذا كنت لا تريد الاحتفاظ به طويلاً
            # del generated_codes[user_code] 

            await update.message.reply_text(f"تهانينا! تم إضافتك بنجاح إلى المجموعة.")

        except BadRequest as e:
            logger.error(f"BadRequest when trying to add user {user.id} to group {target_group_id}: {e.message}")
            if "user is already a member" in e.message.lower() or "user_not_participant" in e.message.lower(): # قد تختلف الرسالة
                 await update.message.reply_text("أنت بالفعل عضو في هذه المجموعة أو لا يمكن إضافتك حالياً.")
            elif "chat not found" in e.message.lower() or "group not found" in e.message.lower():
                 await update.message.reply_text(f"خطأ: المجموعة المستهدفة ({target_group_id}) غير موجودة أو لا يمكن الوصول إليها. يرجى إبلاغ المسؤول.")
            else:
                 await update.message.reply_text(f"حدث خطأ أثناء محاولة إضافتك للمجموعة. تأكد أن البوت لديه الصلاحيات اللازمة في المجموعة. الخطأ: {e.message}")
        except Forbidden as e:
            logger.error(f"Forbidden error when trying to add user {user.id} to group {target_group_id}: {e.message}")
            await update.message.reply_text("ليس لدى البوت الصلاحية لإضافتك إلى المجموعة. يرجى إبلاغ المسؤول.")
        except Exception as e:
            logger.error(f"Unexpected error when adding user {user.id} to group {target_group_id} with code {user_code}: {e}")
            await update.message.reply_text("حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو الاتصال بالمسؤول.")
    else:
        await update.message.reply_text("The entered code is incorrect. Please try to enter the code correctly.")


# --- الدالة الرئيسية لتشغيل البوت ---
def main() -> None:
    """تشغيل البوت."""
    # إنشاء كائن Application
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات الأوامر والرسائل
    # فلتر للتمييز بين رسائل الأدمن ورسائل المستخدمين بناءً على أمر /start
    # يمكن للمستخدمين العاديين إرسال /start أو أي نص مباشرة (سيعالج ككود)
    # الأدمن لديه أوامر خاصة
    
    # أوامر الأدمن (تتطلب التحقق من هوية الأدمن داخل الدالة)
    application.add_handler(CommandHandler("start", start_admin, filters=Filters.User(user_id=ADMIN_ID)))
    application.add_handler(CommandHandler("addgroup", add_group_command, filters=Filters.User(user_id=ADMIN_ID)))
    application.add_handler(CommandHandler("generatemembershipcodes", generate_codes_command, filters=Filters.User(user_id=ADMIN_ID)))
    application.add_handler(CommandHandler("listgroups", list_groups_command, filters=Filters.User(user_id=ADMIN_ID)))
    application.add_handler(CommandHandler("listcodes", list_codes_command, filters=Filters.User(user_id=ADMIN_ID)))
    
    # أوامر المستخدم العادي
    # نريد أن يتعامل /start للمستخدم العادي بشكل مختلف عن الأدمن
    # لذلك، لا نضع فلتر ID هنا، بل نتحقق داخل الدالة إذا كان المستخدم هو الأدمن أم لا
    # أو نستخدم فلتر معاكس ~Filters.User(user_id=ADMIN_ID)
    application.add_handler(CommandHandler("start", start_user, filters=~Filters.User(user_id=ADMIN_ID)))
    
    # معالج الرسائل النصية (لمعالجة الأكواد)
    # يجب أن يكون هذا المعالج بعد أوامر الأدمن لتجنب اعتراض الأوامر كنصوص عادية
    # ويجب أن يكون للمستخدمين غير الأدمن، أو يتم التحقق داخله.
    # هنا، نجعله يستقبل من أي مستخدم غير الأدمن، أو إذا كان أدمن ولم يكن الأمر من أوامره
    application.add_handler(MessageHandler(Filters.TEXT & ~Filters.COMMAND & ~Filters.User(user_id=ADMIN_ID), handle_code_message))
    # إذا أرسل الأدمن نصًا ليس أمرًا، يمكن تجاهله أو معالجته بشكل خاص. حاليًا سيتجاهله.

    # تحميل البيانات المخزنة (إذا كنت تستخدم ملفات للتخزين الدائم - هذا مثال، ليس مطبقاً بالكامل)
    # load_data() # ستحتاج لإنشاء هذه الدالة

    # بدء تشغيل البوت
    logger.info("Bot started successfully!")
    application.run_polling()

    # حفظ البيانات عند إيقاف البوت (إذا كنت تستخدم ملفات - هذا مثال)
    # save_data() # ستحتاج لإنشاء هذه الدالة

if __name__ == '__main__':
    # يمكنك هنا تحديد GROUP_ID الافتراضي إذا أردت إضافته عند بدء التشغيل
    # لكن الأفضل إدارته عبر أوامر الأدمن
    # if GROUP_ID_DEFAULT:
    #     registered_groups.add(str(GROUP_ID_DEFAULT)) 
    #     logger.info(f"Default group {GROUP_ID_DEFAULT} added to registered_groups.")
    main()
