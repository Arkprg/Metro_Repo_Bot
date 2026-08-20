import datetime             # Telbot14
import json
import sqlite3
import logging
import os
import jdatetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._application").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connectionpool").setLevel(logging.WARNING)

def load_config():
    try:
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
            logger.info("✅ Configuration successfully loaded.")
            return config
    except FileNotFoundError:
        logger.error("❌ Config file not found.")
        return {}
    except json.JSONDecodeError:
        logger.error("❌ Error reading config file. Please check.")
        return {}

DB_NAME = os.environ.get("DB_NAME", "customers.db")
AUTHORIZED_USER = "989374550876"
AUTHORIZED_USER1 = "989123946459"

def convert_farsi_numbers(text):
    farsi_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(farsi_digits, english_digits)
    return text.translate(translation_table)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Phone, Access FROM Person WHERE Telegram_ID = ?", (str(user_id),))
    result = cursor.fetchone()
    conn.close()
    if result:
        phone, access = result
        if not access:
            await update.message.reply_text("❌ دسترسی شما به ربات غیرفعال شده است.")
            return
        context.user_data['phone'] = phone
        context.user_data['stage'] = 'awaiting_person_id'
        await update.message.reply_text("شما قبلاً وارد شده‌اید. لطفاً شماره پرسنلی را وارد کنید:")
        return
    button = KeyboardButton("🚀 شروع ربات", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    await update.message.reply_text("لطفاً روی دکمه '🚀 شروع ربات' بزنید و شماره خود را ارسال کنید:", reply_markup=reply_markup)
    if not context.user_data.get("stage"):
        context.user_data.clear()

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        context.user_data['phone'] = phone_number
        logger.info(f"Phone : {phone_number}")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT Fname, Access FROM Person WHERE Phone = ?", (phone_number,))
        result = cursor.fetchone()

        if result:
            fname, access = result
            if not access:
                await update.message.reply_text("❌ دسترسی شما به ربات غیرفعال شده است.")
                conn.close()
                return

            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            cursor.execute("UPDATE Person SET Telegram_ID = ?, Chat_ID = ? WHERE Phone = ?", (str(user_id), str(chat_id), phone_number))
            conn.commit()

            await update.message.reply_text("شماره تایید شد. لطفاً شماره پرسنلی را وارد کنید:")
            context.user_data['stage'] = 'awaiting_person_id'
        else:
            await update.message.reply_text("شماره شما در سیستم یافت نشد.")
        conn.close()
    else:
        await update.message.reply_text("لطفاً شماره را با دکمه ارسال کنید.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    user_stage = context.user_data.get('stage')
    phone_number = context.user_data.get('phone')

    if user_stage == 'awaiting_person_id':
        person_id = convert_farsi_numbers(user_text)
        context.user_data['person_id'] = person_id
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT Fname, Family FROM Person WHERE Phone = ? AND Person_ID = ?", (phone_number, person_id))
        result = cursor.fetchone()
        conn.close()

        if result:
            fname, lname = result
            context.user_data['stage'] = 'awaiting_date'
            await update.message.reply_text(f"✅ سلام. {fname} {lname}!")

            if phone_number == AUTHORIZED_USER or phone_number == AUTHORIZED_USER1:
                context.user_data['is_admin'] = True
                admin_keyboard = [
                    [KeyboardButton("ارسال پیام عمومی")],
                    [KeyboardButton("نمایش تریپ‌ها")],
                    [KeyboardButton("ویرایش اطلاعات کاربران")]
                ]
                reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
                await update.message.reply_text("📋 پنل مدیریت فعال است.", reply_markup=reply_markup)
            else:
                await show_calendar(update, context)
        else:
            await update.message.reply_text("❌ شماره پرسنلی نامعتبر است.")
        return

    if context.user_data.get('is_admin'):
        if user_text == "ارسال پیام عمومی":
            await update.message.reply_text("✏️ لطفاً پیام مورد نظر خود را برای ارسال به همه کاربران وارد کنید:")
            context.user_data['stage'] = 'awaiting_broadcast_message'
            return

        elif user_text == "نمایش تریپ‌ها":
            context.user_data['stage'] = 'awaiting_date'
            return await show_calendar(update, context)

        elif user_text == "ویرایش اطلاعات کاربران":
            context.user_data['stage'] = 'awaiting_edit_person_id'
            await update.message.reply_text("🔢 لطفاً شماره پرسنلی کاربر را وارد کنید:")
            return

        elif user_stage == 'awaiting_broadcast_message':
            context.user_data['stage'] = None
            return await broadcast_message(update, context)

        elif user_stage == 'awaiting_edit_person_id':
            person_id = convert_farsi_numbers(user_text)
            context.user_data['edit_person_id'] = person_id
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT Fname, Family, Phone, Access FROM Person WHERE Person_ID = ?", (person_id,))
            result = cursor.fetchone()
            conn.close()
            if result:
                fname, lname, phone, access = result
                status_text = "فعال" if access else "غیرفعال"
                await update.message.reply_text(f"{fname} {lname} \n\nشماره فعلی: {phone}\nوضعیت فعلی: {status_text}\nلطفاً شماره جدید یا یکی از گزینه‌های زیر را ارسال کنید:")
                context.user_data['stage'] = 'awaiting_new_user_info'
                context.user_data['edit_phone'] = phone
            else:
                await update.message.reply_text("❌ شماره پرسنلی یافت نشد.")
            return

        elif user_stage == 'awaiting_new_user_info':
            new_text = convert_farsi_numbers(user_text.strip())
            person_id = context.user_data.get('edit_person_id')

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            if new_text in ['فعال', '1']:
                cursor.execute("UPDATE Person SET Access = 1 WHERE Person_ID = ?", (person_id,))
                conn.commit()
                await update.message.reply_text("✅ وضعیت کاربر به فعال تغییر یافت.")
            elif new_text in ['غیرفعال', '0']:
                cursor.execute("UPDATE Person SET Access = 0 WHERE Person_ID = ?", (person_id,))
                conn.commit()
                await update.message.reply_text("✅ وضعیت کاربر به غیرفعال تغییر یافت.")
            elif new_text.startswith("09") or new_text.startswith("989"):
                cursor.execute("UPDATE Person SET Phone = ? WHERE Person_ID = ?", (new_text, person_id))
                conn.commit()
                await update.message.reply_text("✅ شماره تلفن بروزرسانی شد.")
            else:
                await update.message.reply_text("❗ ورودی نامعتبر است. لطفاً شماره یا وضعیت صحیح وارد کنید.")
            conn.close()
            context.user_data['stage'] = None
            return

    await update.message.reply_text("❗ لطفاً ابتدا روی دکمه start کلیک کنید. \n \n /start")

async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    iran_tz = pytz.timezone("Asia/Tehran")
    now = datetime.datetime.now(iran_tz)
    today = jdatetime.datetime.fromgregorian(datetime=now).date()
    start_day = today - jdatetime.timedelta(days=3)
    end_day = today + jdatetime.timedelta(days=1)

    days_buttons = []
    current_day = start_day
    while current_day <= end_day:
        weekday_name = current_day.strftime("%A")  # نام روز هفته به انگلیسی
        farsi_weekdays = {
            "Saturday": "شنبه",
            "Sunday": "یک‌شنبه",
            "Monday": "دوشنبه",
            "Tuesday": "سه‌شنبه",
            "Wednesday": "چهارشنبه",
            "Thursday": "پنج‌شنبه",
            "Friday": "جمعه",
        }
        weekday_fa = farsi_weekdays.get(weekday_name, "")
        label = f"📆 {weekday_fa} {current_day.strftime('%Y/%m/%d')}"
        btn = InlineKeyboardButton(label, callback_data=current_day.strftime("%Y/%m/%d"))
        days_buttons.append([btn])
        current_day += jdatetime.timedelta(days=1)

    weekday_en = today.strftime('%A')
    weekday_fa = farsi_weekdays.get(weekday_en, weekday_en)
    reply_markup = InlineKeyboardMarkup(days_buttons)
    if isinstance(update, Update):
        await update.message.reply_text(f"📆 امروز {weekday_fa} : {today.strftime('%Y/%m/%d')}\n\nلطفا تاریخ موردنظر را انتخاب کنید:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"📆 امروز {weekday_fa} : {today.strftime('%Y/%m/%d')}\n\nلطفا تاریخ موردنظر را انتخاب کنید:", reply_markup=reply_markup)

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    selected_date = query.data

    if selected_date == "back_calendar":
        await show_calendar(query, context)
        return

    await query.answer()

    phone_number = context.user_data.get("phone")
    person_id = context.user_data.get("person_id")
    logger.info(f" {person_id} : Selected Date: {selected_date}")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Person.Fname, Trip1, Trip2, Trip3, Trip4, Trip5, Trip6
        FROM Person
        JOIN Trips ON Person.Person_ID = Trips.Person_ID
        WHERE Person.Phone = ? AND Trips.Person_ID = ? AND Trips.Tarikh = ?
    """, (phone_number, person_id, selected_date))
    result = cursor.fetchone()
    conn.close()

    if result:
        name, *trips = result
        valid_trips = [trip for trip in trips if trip]
        response_text = "\n".join(valid_trips) if valid_trips else "هیچ تریپی ثبت نشده است."
    else:
        response_text = f"\n هیچ اطلاعاتی برای این تاریخ یافت نشد."
        if person_id is None or phone_number is None:
            await query.answer()
            await query.message.reply_text("❗اطلاعات شما ناقص است.\n لطفاً روی دکمه '🚀 شروع ربات' بزنید و شماره خود را مجدد ارسال کنید. \n \n /start")
            await start(update, context)
            return

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_calendar")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f" تریپ های شما در تاریخ {selected_date}:\n{response_text}", reply_markup=reply_markup)

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Chat_ID FROM Person WHERE Chat_ID IS NOT NULL")
    chat_ids = cursor.fetchall()
    conn.close()

    count = 0
    for (chat_id,) in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(chat_id), text=message)
            count += 1
        except Exception as e:
            logger.warning(f"❗ Failed to send message to {chat_id}: {e}")

    await update.message.reply_text(f"✅ پیام به {count} کاربر ارسال شد.")

async def receive_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone_number = context.user_data.get("phone")
    if phone_number != AUTHORIZED_USER:
        await update.message.reply_text("❌ شما مجاز نیستید.")
        return

    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    file_path = f"./{DB_NAME}"
    await file.download_to_drive(file_path)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Trips LIMIT 1;")
        cursor.execute("SELECT * FROM Person LIMIT 1;")
        conn.close()
        await update.message.reply_text("✅ دیتابیس بروز رسانی شد.")
    except sqlite3.Error:
        conn.close()
        await update.message.reply_text("❌ دیتابیس معتبر نیست.")

# ---- اجرای ربات ----
def main():
    config = load_config()
    token = config.get("BOT_TOKEN")
    if not token:
        logger.error("❌ Robot token not found. Please check the config file.")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.FileExtension("db"), receive_database))
    application.add_handler(CallbackQueryHandler(date_selected))

    application.run_polling()

if __name__ == "__main__":
    main()
