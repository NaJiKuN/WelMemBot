#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# تحميل المتغيرات البيئية
load_dotenv()

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("Error: BOT_TOKEN not found in .env file")
    sys.exit(1)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# نموذج قاعدة البيانات
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    joined_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)

# إعداد قاعدة البيانات
def setup_db():
    try:
        db_path = Path(__file__).parent / "bot_data.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        return engine
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        sys.exit(1)

# معالجة الأمر /start
async def start(update: Update, context):
    try:
        await update.message.reply_text("مرحباً بك في البوت!")
    except Exception as e:
        logger.error(f"Error in start: {e}")

# المعالجة الرئيسية
async def main():
    try:
        # إعداد البوت
        engine = setup_db()
        Session = sessionmaker(bind=engine)
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # تسجيل المعالجات
        app.add_handler(CommandHandler("start", start))
        
        # بدء البوت
        await app.initialize()
        await app.start()
        logger.info("Bot started successfully")
        
        # انتظار حتى الإغلاق
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # إدارة الإشارات
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # التشغيل
    asyncio.run(main())
