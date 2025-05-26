# x2.7
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json
import random
import string

# المتغيرات الأساسية
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
CODES_FILE = 'codes.json'

# حالات المحادثة
ADMIN_WAITING_FOR_BUTTON = 'admin_waiting_for_button'
ADMIN_ASK_GROUP_ID = 'admin_ask_group_id'
ADMIN_ASK_NUM_CODES = 'admin_ask_num_codes'
USER_WAITING_FOR_BUTTON = 'user_waiting_for_button'
USER_ASK_CODE = 'user_ask_code'

# دالة لتوليد الأكواد
def generate_code(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# دالة لإضافة الأكواد إلى ملف JSON
def add_codes(group_id, num_codes):
    codes = [generate_code() for _ in range(num_codes)]
    try:
        with open(CODES_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    group_id_str = str(group_id)
    if group_id_str not in data:
        data[group_id_str] = []
    data[group_id_str].extend(codes)
    with open(CODES_FILE, 'w') as f:
        json.dump(data, f)
    return codes

# دالة للتحقق من الأكواد وإزالتها بعد الاستخدام
def find_and_remove_code(code):
    try:
        with open(CODES_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    for group_id, codes in data.items():
        if code in codes:
            data[group_id].remove(code)
            with open(CODES_FILE, 'w') as f:
                json.dump(data, f)
            return group_id
    return None

# دالة لإضافة المستخدم إلى المجموعة
def add_user_to_group(bot, user_id, group_id):
    bot.add_chat_member(chat_id=group_id, user_id=user_id)

# دالة لإرسال رسالة الترحيب
def send_welcome_message(bot, group_id, user_name):
    message = f"Welcome, {user_name}!\nYour membership will automatically expire in one month.\nPlease adhere to the group rules and avoid leaving before the specified period to prevent suspension."
    bot.send_message(chat_id=group_id, text=message)

# دالة بدء المحادثة
def start(update, context):
    if update.message.from_user.id == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("Generate Codes", callback_data='generate')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Welcome, admin! What would you like to do?', reply_markup=reply_markup)
        return ADMIN_WAITING_FOR_BUTTON
    else:
        keyboard = [[InlineKeyboardButton("Enter Code", callback_data='enter_code')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Welcome to WelMemBot! Please enter your code to join the group:', reply_markup=reply_markup)
        return USER_WAITING_FOR_BUTTON

# دالة لمعالجة الأزرار
def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'generate':
        if query.from_user.id == ADMIN_ID:
            query.edit_message_text(text='Please enter the group ID (e.g., -1002329495586):')
            return ADMIN_ASK_GROUP_ID
        else:
            query.edit_message_text(text='You are not authorized.')
            return ConversationHandler.END
    elif query.data == 'enter_code':
        query.edit_message_text(text='Please enter your code:')
        return USER_ASK_CODE

# دالة لاستلام معرف المجموعة من المسؤول
def get_group_id(update, context):
    group_id = update.message.text
    context.user_data['group_id'] = group_id
    update.message.reply_text('Please enter the number of codes to generate:')
    return ADMIN_ASK_NUM_CODES

# دالة لاستلام عدد الأكواد من المسؤول
def get_num_codes(update, context):
    try:
        num_codes = int(update.message.text)
    except ValueError:
        update.message.reply_text('Please enter a valid number.')
        return ADMIN_ASK_NUM_CODES
    group_id = context.user_data['group_id']
    codes = add_codes(group_id, num_codes)
    update.message.reply_text(f'{num_codes} codes have been generated for group {group_id}:\n' + '\n'.join(codes))
    return ConversationHandler.END

# دالة لاستلام الكود من المستخدم
def get_code(update, context):
    code = update.message.text
    user_id = update.message.from_user.id
    group_id_str = find_and_remove_code(code)
    if group_id_str:
        group_id = int(group_id_str)
        add_user_to_group(context.bot, user_id, group_id)
        user_name = update.message.from_user.first_name
        send_welcome_message(context.bot, group_id, user_name)
        update.message.reply_text('You have been added to the group.')
    else:
        update.message.reply_text('The entered code is incorrect. Please try entering the code correctly.')
    return ConversationHandler.END

# إعداد ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        ADMIN_WAITING_FOR_BUTTON: [CallbackQueryHandler(button)],
        ADMIN_ASK_GROUP_ID: [MessageHandler(Filters.text & ~Filters.command, get_group_id)],
        ADMIN_ASK_NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, get_num_codes)],
        USER_WAITING_FOR_BUTTON: [CallbackQueryHandler(button)],
        USER_ASK_CODE: [MessageHandler(Filters.text & ~Filters.command, get_code)],
    },
    fallbacks=[],
)

# الجزء الرئيسي لتشغيل البوت
if __name__ == '__main__':
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()
