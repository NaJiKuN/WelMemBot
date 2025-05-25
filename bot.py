import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.error import TelegramError
import random
import string
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Load environment variables
load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "WelMemBot"
ADMIN_IDS = [764559466]
INVITE_LINK = "https://t.me/+BgsrjW-Y8qtkOTY0"
WELCOME_MESSAGE = """
Welcome, {username}!
Your membership will automatically expire after 1 month.
Please adhere to the group rules.
"""
DB_PATH = Path(__file__).parent / "invite_codes.db"
DB_URL = f"sqlite:///{DB_PATH}"

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()

class InviteCode(Base):
    __tablename__ = 'invite_codes'
    code = Column(String, primary_key=True)
    used = Column(Boolean, default=False)
    used_by = Column(Integer)
    used_at = Column(DateTime)
    expires_at = Column(DateTime)

class GroupSettings(Base):
    __tablename__ = 'group_settings'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer)
    group_name = Column(String)

class Member(Base):
    __tablename__ = 'members'
    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    joined_at = Column(DateTime)
    expires_at = Column(DateTime)

def init_db():
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_code ON invite_codes(code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_id ON members(user_id)"))
    return engine

engine = init_db()
Session = sessionmaker(bind=engine)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def generate_random_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def start(update: Update, context):
    if is_admin(update.effective_user.id):
        keyboard = [
            [InlineKeyboardButton("Generate Codes", callback_data='generate_codes')],
            [InlineKeyboardButton("Set Group", callback_data='set_group')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Admin Panel:', reply_markup=reply_markup)
    else:
        await update.message.reply_text('Please enter your invite code:')

async def handle_invite_code(update: Update, context):
    user_code = update.message.text.upper().strip()
    user = update.effective_user
    
    try:
        with Session() as session:
            code = session.query(InviteCode).filter_by(code=user_code).first()
            if not code or code.used or code.expires_at < datetime.now():
                await update.message.reply_text("❌ Invalid code")
                return

            group = session.query(GroupSettings).first()
            if not group:
                await update.message.reply_text("Group not configured")
                return

            try:
                member = await context.bot.get_chat_member(group.group_id, user.id)
                if member.status in ['member', 'administrator', 'creator']:
                    await update.message.reply_text("You're already a member!")
                    return
            except TelegramError:
                pass

            code.used = True
            code.used_by = user.id
            code.used_at = datetime.now()

            new_member = Member(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                joined_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=30)
            session.add(new_member)
            session.commit()

        await update.message.reply_text(f"✅ Verified!\nJoin here: {INVITE_LINK}")
        await context.bot.send_message(
            chat_id=group.group_id,
            text=WELCOME_MESSAGE.format(username=user.username or user.first_name)
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await update.message.reply_text("An error occurred")

async def check_expired_members(context):
    try:
        with Session() as session:
            expired = session.query(Member).filter(Member.expires_at < datetime.now()).all()
            group = session.query(GroupSettings).first()
            if not group:
                return

            for member in expired:
                try:
                    await context.bot.ban_chat_member(group.group_id, member.user_id)
                    session.delete(member)
                except TelegramError as e:
                    logger.error(f"Failed to remove {member.user_id}: {str(e)}")
            session.commit()
    except Exception as e:
        logger.error(f"Error in check_expired_members: {str(e)}")

def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expired_members, 'interval', hours=24, args=[None])
    scheduler.start()

    signal.signal(signal.SIGINT, lambda s, f: (scheduler.shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (scheduler.shutdown(), sys.exit(0)))

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invite_code))
    app.add_error_handler(lambda u, c: logger.error(f"Update {u} caused error {c.error}"))

    app.run_polling()
    logger.info("Bot started")

if __name__ == '__main__':
    main()
