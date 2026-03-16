import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "안녕하세요! 저는 AI 에이전트 봇입니다. 메시지를 보내주세요!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "사용 가능한 명령어:\n"
        "/start - 봇 시작\n"
        "/help - 도움말"
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text(f"받은 메시지: {user_text}")

def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("봇이 시작되었습니다...")
    app.run_polling()

if __name__ == "__main__":
    main()
