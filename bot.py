import os
import logging
import asyncio
from datetime import datetime, time
import pytz
import anthropic
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
EGYPT_TZ        = pytz.timezone("Africa/Cairo")

db     = Database()
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def ask_claude(prompt: str, system: str = "") -> str:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=system or "أنت مساعد روحاني دافئ ومحفز باللغة العربية.",
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

def generate_morning_message() -> str:
    return ask_claude(
        "اكتب رسالة صباحية لبوت امتنان إسلامي. الرسالة تحتوي على:\n"
        "1. تحية صباحية دافئة\n"
        "2. نعمة واحدة من نعم الله\n"
        "3. آية قرآنية مرتبطة بهذه النعمة مع ذكر اسم السورة والآية\n"
        "4. 3 تطبيقات عملية بسيطة لتذكر هذه النعمة اليوم\n"
        "5. في نهاية الرسالة اكتب بالضبط: 'في المساء سأسألك كيف كان يومك 🌙'\n\n"
        "اكتب بأسلوب دافئ وقريب من القلب.",
        system="أنت بوت امتنان إسلامي دافئ. تكتب بالعربية الفصحى البسيطة المفهومة."
    )

def generate_evening_message(morning_blessing: str) -> str:
    return ask_claude(
        f"نعمة اليوم كانت: {morning_blessing}\n\n"
        "اكتب رسالة مسائية تحتوي على سؤالين فقط:\n"
        "1. سؤال عن يوم المستخدم بشكل عام\n"
        "2. سؤال عن نعمة اليوم: هل طبّق أحد التطبيقات العملية؟\n\n"
        "اجعل الرسالة قصيرة ودافئة.",
        system="أنت بوت امتنان إسلامي دافئ. تكتب بالعربية الفصحى البسيطة."
    )

def generate_encouragement(user_reply: str) -> str:
    return ask_claude(
        f"المستخدم رد بهذا على سؤال المساء: '{user_reply}'\n\n"
        "اكتب رداً تشجيعياً قصيراً (3-4 سطور فقط) دافئاً.\n"
        "ثم أضف في نهاية الرد:\n"
        "✨ الشات هيقفل دلوقتي.. موعدنا بكرة الساعة 9 الصبح بنعمة جديدة إن شاء الله 🌅",
        system="أنت بوت امتنان إسلامي دافئ. ردودك قصيرة وحقيقية."
    )

def generate_reminder() -> str:
    return ask_claude(
        "اكتب رسالة تذكير لطيفة لمستخدم لم يرد على سؤال المساء بعد 3 ساعات.\n"
        "الرسالة قصيرة (سطرين أو ثلاثة).",
        system="أنت بوت امتنان إسلامي دافئ."
    )

async def send_morning_messages(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    if not users:
        return
    blessing_text = generate_morning_message()
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=blessing_text)
            db.set_morning_sent(user_id, blessing_text)
            db.set_user_state(user_id, "waiting_evening")
            logger.info(f"Morning message sent to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send morning to {user_id}: {e}")

async def send_evening_messages(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    for user_id in users:
        state = db.get_user_state(user_id)
        if state != "waiting_evening":
            continue
        try:
            blessing = db.get_morning_blessing(user_id) or "نعمة الله"
            evening_msg = generate_evening_message(blessing)
            await context.bot.send_message(chat_id=user_id, text=evening_msg)
            db.set_user_state(user_id, "waiting_reply")
            db.set_evening_sent_time(user_id)
            logger.info(f"Evening message sent to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send evening to {user_id}: {e}")

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    now = datetime.now(EGYPT_TZ)
    for user_id in users:
        state = db.get_user_state(user_id)
        if state != "waiting_reply":
            continue
        evening_time = db.get_evening_sent_time(user_id)
        if not evening_time:
            continue
        hours_passed = (now - evening_time).total_seconds() / 3600
        reminded = db.was_reminded(user_id)
        if hours_passed >= 3 and not reminded:
            try:
                reminder = generate_reminder()
                await context.bot.send_message(chat_id=user_id, text=reminder)
                db.set_reminded(user_id)
                logger.info(f"Reminder sent to {user_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")

async def test_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.user_exists(user_id):
        await update.message.reply_text("اكتب /start الأول 🌸")
        return
    await update.message.reply_text("⏳ جاري توليد رسالة الصبح...")
    blessing = generate_morning_message()
    await update.message.reply_text(blessing)
    db.set_morning_sent(user_id, blessing)
    db.set_user_state(user_id, "waiting_evening")

async def test_evening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.user_exists(user_id):
        await update.message.reply_text("اكتب /start الأول 🌸")
        return
    await update.message.reply_text("⏳ جاري توليد رسالة المساء...")
    blessing = db.get_morning_blessing(user_id) or "نعمة الله"
    evening_msg = generate_evening_message(blessing)
    await update.message.reply_text(evening_msg)
    db.set_user_state(user_id, "waiting_reply")
    db.set_evening_sent_time(user_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.first_name or "صديقي")
    welcome = (
        f"أهلاً وسهلاً {user.first_name or 'صديقي'} 🌸\n\n"
        "أنا بوت الامتنان، رفيقك اليومي لتذكّر نعم الله ☀️\n\n"
        "كل يوم هبعتلك:\n"
        "🌅 الساعة 9 الصبح: نعمة + آية + تطبيقات عملية\n"
        "🌙 الساعة 6 المساء: أسألك عن يومك ونعمة الصبح\n\n"
        "موعدنا بكرة الصبح إن شاء الله ✨\n"
        "اللهم اجعلنا من الشاكرين 🤲"
    )
    await update.message.reply_text(welcome)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not db.user_exists(user_id):
        await update.message.reply_text("أهلاً! اضغط /start للاشتراك في بوت الامتنان 🌸")
        return
    state = db.get_user_state(user_id)
    if state == "waiting_reply":
        encouragement = generate_encouragement(text)
        await update.message.reply_text(encouragement)
        db.set_user_state(user_id, "closed")
        db.clear_evening_data(user_id)
    elif state == "closed":
        await update.message.reply_text(
            "جزاك الله خيراً 🌙\nالشات مقفول دلوقتي.. موعدنا بكرة الساعة 9 الصبح بنعمة جديدة إن شاء الله 🌅"
        )
    else:
        await update.message.reply_text("خد راحتك 😊\nهجيلك الصبح بنعمة جديدة إن شاء الله 🌅")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("morning", test_morning))
    app.add_handler(CommandHandler("evening", test_evening))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    job_queue = app.job_queue
    job_queue.run_daily(send_morning_messages, time=time(9, 0, tzinfo=EGYPT_TZ))
    job_queue.run_daily(send_evening_messages, time=time(18, 0, tzinfo=EGYPT_TZ))
    job_queue.run_repeating(send_reminders, interval=1800, first=60)
    logger.info("بوت الامتنان شغّال ✅")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
