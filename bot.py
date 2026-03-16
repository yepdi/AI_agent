import os
import json
import logging
from datetime import datetime, date, timedelta
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATA_FILE = "data.json"
KST = pytz.timezone("Asia/Seoul")

WAITING_FOR_DATE = 1
WAITING_FOR_TIME = 2


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_pregnancy_info(due_date: date):
    today = date.today()
    days_left = (due_date - today).days
    conception_date = due_date - timedelta(days=280)
    days_pregnant = (today - conception_date).days
    week = days_pregnant // 7
    day_of_week = days_pregnant % 7

    if week < 13:
        trimester = "1삼분기 (초기)"
    elif week < 28:
        trimester = "2삼분기 (중기)"
    else:
        trimester = "3삼분기 (후기)"

    return {
        "days_left": days_left,
        "week": week,
        "day_of_week": day_of_week,
        "trimester": trimester,
    }


def build_status_message(info: dict, due_date: date) -> str:
    days_left = info["days_left"]
    week = info["week"]
    day_of_week = info["day_of_week"]
    trimester = info["trimester"]

    if days_left < 0:
        return (
            f"🎉 출산 예정일({due_date.strftime('%Y년 %m월 %d일')})이 지났어요!\n"
            f"건강하고 행복한 출산을 축하드립니다! 💕"
        )
    elif days_left == 0:
        return "🌟 오늘이 출산 예정일이에요! 건강하고 순산하시길 응원합니다! 💕"
    else:
        return (
            f"👶 출산 예정일까지 D-{days_left}일\n\n"
            f"📅 출산 예정일: {due_date.strftime('%Y년 %m월 %d일')}\n"
            f"🤰 현재 임신 {week}주 {day_of_week}일차\n"
            f"📊 {trimester}\n\n"
            f"오늘도 건강하고 행복한 하루 보내세요! 💕"
        )


async def daily_notification(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    for chat_id, user_data in data.items():
        try:
            due_date = date.fromisoformat(user_data["due_date"])
            info = get_pregnancy_info(due_date)
            msg = "🌅 좋은 아침이에요!\n\n" + build_status_message(info, due_date)
            await context.bot.send_message(chat_id=int(chat_id), text=msg)
        except Exception as e:
            logger.error(f"알림 전송 실패 ({chat_id}): {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "안녕하세요! 👶 출산 예정일 알림 봇이에요.\n\n"
        "사용 가능한 명령어:\n"
        "/setduedate - 출산 예정일 설정\n"
        "/status - 현재 임신 정보 확인\n"
        "/settime - 알림 시간 변경 (기본: 매일 아침 8시)\n"
        "/stop - 알림 중단\n"
        "/help - 도움말"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 명령어 안내\n\n"
        "/setduedate - 출산 예정일 등록/변경\n"
        "/status - 현재 임신 주차 및 D-day 확인\n"
        "/settime - 매일 알림 받을 시간 설정\n"
        "/stop - 알림 중단\n"
        "/start - 처음으로 돌아가기"
    )


async def setduedate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "출산 예정일을 입력해주세요.\n"
        "형식: YYYY-MM-DD (예: 2025-06-15)"
    )
    return WAITING_FOR_DATE


async def setduedate_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        due_date = date.fromisoformat(text)
    except ValueError:
        await update.message.reply_text(
            "날짜 형식이 올바르지 않아요. 다시 입력해주세요.\n예: 2025-06-15"
        )
        return WAITING_FOR_DATE

    chat_id = str(update.effective_chat.id)
    data = load_data()
    if chat_id not in data:
        data[chat_id] = {}
    data[chat_id]["due_date"] = due_date.isoformat()
    if "notify_hour" not in data[chat_id]:
        data[chat_id]["notify_hour"] = 8
        data[chat_id]["notify_minute"] = 0
    save_data(data)

    schedule_notification(context.application, chat_id, data[chat_id])

    info = get_pregnancy_info(due_date)
    msg = f"✅ 출산 예정일이 {due_date.strftime('%Y년 %m월 %d일')}로 설정되었어요!\n\n"
    msg += build_status_message(info, due_date)
    msg += f"\n\n매일 오전 {data[chat_id]['notify_hour']}시에 알림을 보내드릴게요. (/settime 으로 변경 가능)"
    await update.message.reply_text(msg)
    return ConversationHandler.END


async def setduedate_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("취소되었습니다.")
    return ConversationHandler.END


async def settime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_data()
    if chat_id not in data or "due_date" not in data[chat_id]:
        await update.message.reply_text("먼저 /setduedate 로 출산 예정일을 설정해주세요.")
        return ConversationHandler.END
    await update.message.reply_text(
        "알림을 받을 시간을 입력해주세요 (0~23 사이 숫자).\n예: 8 (오전 8시)"
    )
    return WAITING_FOR_TIME


async def settime_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        hour = int(text)
        if not (0 <= hour <= 23):
            raise ValueError
    except ValueError:
        await update.message.reply_text("0에서 23 사이의 숫자를 입력해주세요.")
        return WAITING_FOR_TIME

    chat_id = str(update.effective_chat.id)
    data = load_data()
    data[chat_id]["notify_hour"] = hour
    data[chat_id]["notify_minute"] = 0
    save_data(data)

    schedule_notification(context.application, chat_id, data[chat_id])
    await update.message.reply_text(f"✅ 알림 시간이 매일 {hour}시로 설정되었어요!")
    return ConversationHandler.END


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_data()
    if chat_id not in data or "due_date" not in data[chat_id]:
        await update.message.reply_text("먼저 /setduedate 로 출산 예정일을 설정해주세요.")
        return
    due_date = date.fromisoformat(data[chat_id]["due_date"])
    info = get_pregnancy_info(due_date)
    await update.message.reply_text(build_status_message(info, due_date))


async def stop_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    job_name = f"notify_{chat_id}"
    current_jobs = context.application.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("알림이 중단되었습니다. /setduedate 로 다시 시작할 수 있어요.")


def schedule_notification(app, chat_id: str, user_data: dict):
    job_name = f"notify_{chat_id}"
    current_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    hour = user_data.get("notify_hour", 8)
    minute = user_data.get("notify_minute", 0)

    app.job_queue.run_daily(
        daily_notification,
        time=datetime.now(KST).replace(hour=hour, minute=minute, second=0, microsecond=0).timetz(),
        name=job_name,
    )
    logger.info(f"알림 스케줄 등록: chat_id={chat_id}, {hour}:{minute:02d} KST")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")

    app = ApplicationBuilder().token(TOKEN).build()

    setduedate_handler = ConversationHandler(
        entry_points=[CommandHandler("setduedate", setduedate_start)],
        states={
            WAITING_FOR_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setduedate_receive)],
        },
        fallbacks=[CommandHandler("cancel", setduedate_cancel)],
    )

    settime_handler = ConversationHandler(
        entry_points=[CommandHandler("settime", settime_start)],
        states={
            WAITING_FOR_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, settime_receive)],
        },
        fallbacks=[CommandHandler("cancel", setduedate_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop_notifications))
    app.add_handler(setduedate_handler)
    app.add_handler(settime_handler)

    data = load_data()
    for chat_id, user_data in data.items():
        if "due_date" in user_data:
            schedule_notification(app, chat_id, user_data)

    logger.info("봇이 시작되었습니다...")
    app.run_polling()


if __name__ == "__main__":
    main()
