import os
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

import pytz
import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
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
        trimester = "임신 초기 (1~12주)"
    elif week < 28:
        trimester = "임신 중기 (13~27주)"
    else:
        trimester = "임신 후기 (28주~)"

    return {
        "days_left": days_left,
        "week": week,
        "day_of_week": day_of_week,
        "trimester": trimester,
    }


WEEKLY_TIPS = {
    1:  "아직 임신 초초기예요. 엽산을 꼭 챙겨 드세요!",
    2:  "수정이 이루어지는 시기예요. 몸을 따뜻하게 유지해 주세요.",
    3:  "착상이 시작되는 시기예요. 과격한 운동은 피해 주세요.",
    4:  "임신이 확인되는 주차예요. 산부인과 첫 방문을 준비해 보세요.",
    5:  "심장이 뛰기 시작해요! 입덧이 시작될 수 있어요.",
    6:  "아기 뇌와 척추가 형성돼요. 엽산 섭취가 매우 중요한 시기예요.",
    7:  "아기 팔다리가 생기기 시작해요. 충분한 수분 섭취를 해주세요.",
    8:  "아기 손가락이 만들어지고 있어요. 카페인은 줄여 주세요.",
    9:  "아기가 올리브 크기 정도예요. 피로감이 심할 수 있어요, 충분히 쉬세요.",
    10: "아기 손톱이 생기기 시작해요. 균형 잡힌 식사가 중요해요.",
    11: "아기가 활발하게 움직이기 시작해요. 가벼운 산책을 해보세요.",
    12: "입덧이 조금씩 줄어드는 시기예요. 1차 기형아 검사를 확인해 보세요.",
    13: "안정기에 접어들었어요! 소중한 태교를 시작해 보세요.",
    14: "아기 얼굴 근육이 발달해요. 태교 음악을 들려주세요.",
    15: "아기가 빛을 느낄 수 있어요. 따뜻한 햇볕 산책을 즐겨 보세요.",
    16: "아기 청각이 발달해요. 말을 많이 걸어주세요!",
    17: "태동을 처음 느낄 수 있는 시기예요. 아기의 움직임에 집중해 보세요.",
    18: "아기가 하품하고 삼키는 연습을 해요. 산모 체중 관리를 시작해 보세요.",
    19: "아기 감각기관이 발달해요. 독서 태교를 해보세요.",
    20: "임신 절반을 지났어요! 정밀 초음파 검사를 받아보세요.",
    21: "아기가 점점 통통해지고 있어요. 철분제 섭취를 꼭 챙기세요.",
    22: "아기 눈썹과 속눈썹이 생겨요. 충분한 수면이 중요해요.",
    23: "아기가 소리에 반응해요. 좋아하는 음악을 들려주세요.",
    24: "아기 폐가 발달해요. 임신성 당뇨 검사를 고려해 보세요.",
    25: "아기가 점점 통통해지고 있어요. 손발 부종에 주의하세요.",
    26: "아기 눈이 빛에 반응해요. 하루 30분 걷기를 해보세요.",
    27: "중기 마지막 주예요. 태동 패턴에 익숙해져 보세요.",
    28: "후기가 시작됐어요! 분만 준비 교실을 알아봐도 좋아요.",
    29: "아기가 많은 칼슘이 필요해요. 유제품을 충분히 드세요.",
    30: "아기가 머리를 아래로 돌리기 시작해요. 출산 준비를 시작해 보세요.",
    31: "아기 뇌가 빠르게 발달해요. 스트레스를 줄이고 푹 쉬세요.",
    32: "아기 폐 성숙이 빨라져요. 숨쉬기 운동을 해보세요.",
    33: "아기가 잠자는 패턴이 생겨요. 병원 가방을 준비해 보세요.",
    34: "아기 면역 체계가 강해져요. 출산 계획서를 작성해 보세요.",
    35: "아기가 꽉 차오르고 있어요. 매주 산부인과 방문을 권장해요.",
    36: "아기가 거의 완성됐어요! 모유 수유 준비를 해보세요.",
    37: "이제 만삭이에요! 언제 아기가 나와도 이상하지 않아요.",
    38: "아기가 본능적으로 젖 빠는 연습을 해요. 신생아 용품을 점검해 보세요.",
    39: "진통 신호를 잘 알아두세요. 규칙적 진통이 오면 병원으로!",
    40: "예정일이에요! 아기와의 만남을 기대해 주세요. 곧 만나요! 💕",
}


def get_weekly_tip(week: int) -> str:
    if week <= 0:
        return "아주 초기 임신이에요. 몸을 잘 챙겨 주세요!"
    if week > 40:
        return "예정일이 지났어요. 곧 아기를 만날 수 있어요!"
    return WEEKLY_TIPS.get(week, "건강하고 행복한 임신 기간 보내세요!")


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
        tip = get_weekly_tip(week)
        return (
            f"👶 출산 예정일까지 D-{days_left}일\n\n"
            f"📅 출산 예정일: {due_date.strftime('%Y년 %m월 %d일')}\n"
            f"🤰 현재 임신 {week}주 {day_of_week}일차\n"
            f"📊 {trimester}\n\n"
            f"💡 이번 주 정보\n{tip}\n\n"
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

    schedule_notification(ptb_app, chat_id, data[chat_id])

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

    schedule_notification(ptb_app, chat_id, data[chat_id])
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
    current_jobs = ptb_app.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("알림이 중단되었습니다. /setduedate 로 다시 시작할 수 있어요.")


def schedule_notification(app: Application, chat_id: str, user_data: dict):
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


def build_ptb_app() -> Application:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")

    app = ApplicationBuilder().token(TOKEN).updater(None).build()

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

    return app


ptb_app = build_ptb_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ptb_app.initialize()
    await ptb_app.start()

    domain = (
        os.environ.get("REPLIT_DEV_DOMAIN")
        or (os.environ.get("REPLIT_DOMAINS", "").split(",")[0].strip() or None)
    )
    if domain:
        webhook_url = f"https://{domain}/webhook"
        await ptb_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook 등록 완료: {webhook_url}")
    else:
        logger.warning("도메인 환경 변수가 없어 webhook 등록을 건너뜁니다.")

    saved = load_data()
    for chat_id, user_data in saved.items():
        if "due_date" in user_data:
            schedule_notification(ptb_app, chat_id, user_data)

    yield

    await ptb_app.stop()
    await ptb_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(content="ok")


@app.get("/")
async def root():
    return {"status": "running", "bot": "pregnancy notification bot"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=5000, reload=False)
