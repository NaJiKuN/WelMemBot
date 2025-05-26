# X2.5
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json
import random
import string

# المتغيرات الأساسية
TOKEN = '8034775321:AAHVwntCuBOwDh3NKIPxcs-jGJ9mGq4o0_0'
ADMIN_ID = 764559466
CODES_FILE = 'codes.json'

# حالات المحادثة
GROUP_ID, NUM_CODES = range(2)
CODE = range(1)

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
    if group_id not in data:
        data[group_id] = []
    data[group_id].extend(codes)
    with open(CODES_FILE, 'w') as f:
        json.dump(data, f)
    return codes

# دالة للتحقق من الأكواد
def check_code(group_id, code):
    try:
        with open(CODES_FILE, 'r') as f:
            data = json.load(f)
        if group_id in data and code in data[group_id]:
            data[group_id].remove(code)
            with open(CODES_FILE, 'w') as f:
                json.dump(data, f)
            return True
    except FileNotFoundError:
        pass
    return False

# دالة لإضافة المستخدم إلى المجموعة
def add_user_to_group(bot, user_id, group_id):
    bot.add_chat_member(group_id, user_id)

# دالة لإرسال رسالة الترحيب
def send_welcome_message(bot, group_id, user_name):
    message = f"Welcome, {user_name}!\nYour membership will automatically expire in one month.\nPlease adhere to the group rules and avoid leaving before the specified period to prevent suspension."
    bot.send_message(group_id, message)

# دوال المسؤول
def start_admin(update, context):
    if update.message.from_user.id != ADMIN_ID:
        update.message.reply_text('You are not authorized to use this bot.')
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("Generate Codes", callback_data='generate')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Welcome, admin! What would you like to do?', reply_markup=reply_markup)
    return GROUP_ID

def group_id(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text('Please enter the group ID (e.g., -1002329495586):')
    return GROUP_ID

def group_id_input(update, context):
    group_id = update.message.text
    context.user_data['group_id'] = group_id
    update.message.reply_text('Please enter the number of codes to generate:')
    return NUM_CODES

def num_codes(update, context):
    num_codes = int(update.message.text)
    group_id = context.user_data['group_id']
    codes = add_codes(group_id, num_codes)
    update.message.reply_text(f'{num_codes} codes have been generated for group {group_id}:\n' + '\n'.join(codes))
    return ConversationHandler.END

# دوال المستخدم
def start_user(update, context):
    keyboard = [[InlineKeyboardButton("Enter Code", callback_data='enter_code')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Welcome to WelMemBot! Please enter your code to join the group:', reply_markup=reply_markup)
    return CODE

def code_request(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text('Please enter your code:')
    return CODE

def code_input(update, context):
    code = update.message.text
    user_id = update.message.from_user.id
    # للتبسيط، نفترض مجموعة واحدة. يمكن تعديلها لدعم مجموعات متعددة.
    group_id = '-1002329495586'
    
    if check_code(group_id, code):
        add_user_to_group(context.bot, user_id, group_id)
        user_name = update.message.from_user.first_name
        send_welcome_message(context.bot, group_id, user_name)
        update.message.reply_text('You have been added to the group.')
    else:
        update.message.reply_text('The entered code is incorrect. Please try entering the code correctly.')
    return ConversationHandler.END

# معالجة استجابات الأزرار
def button(update, context):
    query = update.callback_query
    if query.data == 'generate':
        return group_id(update, context)
    elif query.data == 'enter_code':
        return code_request(update, context)

# إعداد ConversationHandler للمسؤول
admin_conv = ConversationHandler(
    entry_points=[CommandHandler('start', start_admin)],
    states={
        GROUP_ID: [MessageHandler(Filters.text & ~Filters.command, group_id_input)],
        NUM_CODES: [MessageHandler(Filters.text & ~Filters.command, num_codes)]
    },
    fallbacks=[]
)

# إعداد ConversationHandler للمستخدمين
user_conv = ConversationHandler(
    entry_points=[CommandHandler('start', start_user)],
    states={
        CODE: [MessageHandler(Filters.text & ~Filters.command, code_input)]
    },
    fallbacks=[]
)

# إعداد Updater و Dispatcher
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

# إضافة المعالجات
dp.add_handler(admin_conv)
dp.add_handler(user_conv)
dp.add_handler(CallbackQueryHandler(button))

# بدء البوت
updater.start_polling()
updater.idle()
