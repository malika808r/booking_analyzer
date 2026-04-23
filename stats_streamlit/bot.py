import os
import asyncio
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from passlib.hash import bcrypt
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# --- DB CONFIG ---
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "booking_db")
DB_USER = os.getenv("DB_USER", "booking_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "booking_password")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
SELECT_TABLE, SELECT_TIME, CONFIRM_BOOKING = range(3)

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_owner = context.user_data.get('is_owner', False)
    reply_keyboard = [["🍴 Menu", "📅 Book Table"]]
    if is_owner:
        reply_keyboard.append(["📈 Owner Summary"])
    reply_keyboard.append(["ℹ️ About"])
    
    await update.message.reply_text(
        "Welcome to the **Booking Analyzer Guest Bot**! 🚀\n\n"
        "Here you can view our current menu and reserve a table instantly.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True),
        parse_mode="Markdown"
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /login <email> <password>")
        return

    email, password = args[0], args[1]
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, role, password_hash FROM users WHERE lower(email) = lower(%s)", (email,))
            user = cur.fetchone()
            
            if user and bcrypt.verify(password, user['password_hash']):
                # Link Telegram ID
                cur.execute("UPDATE users SET telegram_id = %s WHERE id = %s", (update.effective_user.id, user['id']))
                conn.commit()
                if user['role'] == "OWNER":
                    context.user_data['is_owner'] = True
                    context.user_data['owner_id'] = user['id']
                    await update.message.reply_text("✅ Welcome, Owner! You now have access to the dashboard summary.",
                                                 reply_markup=ReplyKeyboardMarkup([["🍴 Menu", "📅 Book Table"], ["📈 Owner Summary"], ["ℹ️ About"]], resize_keyboard=True))
                else:
                    await update.message.reply_text("Admin access denied for this role.")
            else:
                await update.message.reply_text("Invalid email or password.")
    finally:
        conn.close()

async def owner_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_owner'):
        await update.message.reply_text("You must be logged in as an owner to see this.")
        return

    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get first restaurant linked to owner
            cur.execute("SELECT r.id, r.name FROM restaurants r JOIN restaurant_owners ro ON ro.restaurant_id = r.id WHERE ro.owner_user_id = %s LIMIT 1", (context.user_data['owner_id'],))
            res = cur.fetchone()
            if not res:
                await update.message.reply_text("No restaurants linked to your account.")
                return

            cur.execute("SELECT count(*) as count FROM bookings WHERE restaurant_id = %s AND start_time::date = current_date", (res['id'],))
            today_count = cur.fetchone()['count']
            
            cur.execute("SELECT count(*) as count FROM bookings WHERE restaurant_id = %s AND status = 'CANCELLED' AND start_time::date = current_date", (res['id'],))
            cancels = cur.fetchone()['count']

            report = (
                f"📈 *Daily Summary for {res['name']}*\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                f"• Total Bookings Today: *{today_count}*\n"
                f"• Cancellations: *{cancels}*\n"
                f"• System Status: *Online* 🟢\n\n"
                "Check the Streamlit dashboard for full ML forecasts."
            )
            await update.message.reply_text(report, parse_mode="Markdown")
    finally:
        conn.close()

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT b.id, b.start_time, r.name as restaurant, t.label as table_label 
                FROM bookings b
                JOIN restaurants r ON b.restaurant_id = r.id
                JOIN restaurant_tables t ON b.table_id = t.id
                WHERE b.customer_telegram_id = %s AND b.status = 'BOOKED'
                ORDER BY b.start_time ASC
            """, (tg_id,))
            rows = cur.fetchall()
            
            if not rows:
                await update.message.reply_text("You have no active bookings.")
                return

            await update.message.reply_text("📅 *Your Active Bookings:*", parse_mode="Markdown")
            for b in rows:
                time_str = b['start_time'].strftime("%d %b, %H:%M")
                text = f"🏠 {b['restaurant']}\n🕒 {time_str}\n🪑 {b['table_label']}"
                keyboard = [[InlineKeyboardButton("❌ Cancel This Booking", callback_data=f"cancel_{b['id']}")]]
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        conn.close()

async def cancel_booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    booking_id = query.data.replace("cancel_", "")
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE bookings SET status = 'CANCELLED', updated_at = now() WHERE id = %s", (booking_id,))
        conn.commit()
        await query.edit_message_text(text="❌ Booking has been cancelled.")
    finally:
        conn.close()


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get first restaurant for demo
            cur.execute("SELECT id, name FROM restaurants LIMIT 1")
            res = cur.fetchone()
            if not res:
                await update.message.reply_text("No restaurants found in database.")
                return

            cur.execute("""
                SELECT c.name as cat, i.name as item, i.price, i.currency 
                FROM menu_items i 
                JOIN menu_categories c ON i.category_id = c.id
                WHERE c.restaurant_id = %s AND i.is_available = true
                ORDER BY c.sort_order, i.sort_order
            """, (res["id"],))
            items = cur.fetchall()
            
            if not items:
                await update.message.reply_text("The menu is currently empty.")
                return

            menu_text = f"🍴 *{res['name']} Menu*\n\n"
            current_cat = ""
            for item in items:
                if item['cat'] != current_cat:
                    current_cat = item['cat']
                    menu_text += f"\n*--- {current_cat} ---*\n"
                menu_text += f"• {item['item']} - {item['price']} {item['currency']}\n"
            
            await update.message.reply_text(menu_text, parse_mode="Markdown")
    finally:
        conn.close()

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, label, capacity FROM restaurant_tables LIMIT 8")
            tables = cur.fetchall()
            if not tables:
                await update.message.reply_text("No tables available for booking.")
                return ConversationHandler.END

            keyboard = []
            for t in tables:
                keyboard.append([InlineKeyboardButton(f"{t['label']} (up to {t['capacity']} pers.)", callback_data=f"table_{t['id']}||{t['label']}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose a table:", reply_markup=reply_markup)
            return SELECT_TABLE
    finally:
        conn.close()

async def table_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("||")
    context.user_data['table_id'] = data[0].replace("table_", "")
    context.user_data['table_label'] = data[1]
    
    # Generate simple time options for next 3 hours
    keyboard = []
    now = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for i in range(4):
        time_str = (now + timedelta(hours=i)).strftime("%H:%M")
        keyboard.append([InlineKeyboardButton(time_str, callback_data=f"time_{time_str}")])
    
    await query.edit_message_text(
        text=f"Selected {context.user_data['table_label']}. \nNow choose a time for today:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_TIME

async def time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['booking_time'] = query.data.replace("time_", "")
    
    await query.edit_message_text(
        text=f"Final Step: Confirm booking for {context.user_data['table_label']} at {context.user_data['booking_time']}?\n\n"
             f"This will be recorded under your name: {update.effective_user.first_name}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="conf_yes"), 
             InlineKeyboardButton("❌ Cancel", callback_data="conf_no")]
        ])
    )
    return CONFIRM_BOOKING

async def booking_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "conf_yes":
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                # Get restaurant ID
                cur.execute("SELECT restaurant_id FROM restaurant_tables WHERE id = %s", (context.user_data['table_id'],))
                rid = cur.fetchone()[0]
                
                # Create start/end time
                today = datetime.now().date()
                h, m = map(int, context.user_data['booking_time'].split(":"))
                start_dt = datetime.combine(today, datetime.min.time().replace(hour=h, minute=m))
                end_dt = start_dt + timedelta(hours=2)
                
                cur.execute("""
                    INSERT INTO bookings (id, restaurant_id, table_id, party_size, start_time, end_time, status, customer_name, customer_telegram_id)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 'BOOKED', %s, %s)
                """, (rid, context.user_data['table_id'], 2, start_dt, end_dt, update.effective_user.first_name, update.effective_user.id))
                
                # Find owners to notify
                cur.execute("""
                    SELECT u.telegram_id 
                    FROM users u
                    JOIN restaurant_owners ro ON ro.owner_user_id = u.id
                    WHERE ro.restaurant_id = %s AND u.telegram_id IS NOT NULL
                """, (rid,))
                owner_ids = [r[0] for r in cur.fetchall()]
                
            conn.commit()
            await query.edit_message_text("✅ Success! Your table is reserved. See you soon!")
            
            # Send notifications
            msg = f"🔔 *New Booking!*\n👤 {update.effective_user.first_name}\n🕒 {context.user_data['booking_time']}\n🪑 {context.user_data['table_label']}"
            for oid in owner_ids:
                try:
                    await context.bot.send_message(chat_id=oid, text=msg, parse_mode="Markdown")
                except: pass
        except Exception as e:
            logger.error(f"Booking failed: {e}")
            await query.edit_message_text("❌ Error processing your booking. Please try again later.")
        finally:
            conn.close()
    else:
        await query.edit_message_text("Booking cancelled.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    application = Application.builder().token(TOKEN).build()

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Book Table$"), book_start)],
        states={
            SELECT_TABLE: [CallbackQueryHandler(table_selected, pattern="^table_")],
            SELECT_TIME: [CallbackQueryHandler(time_selected, pattern="^time_")],
            CONFIRM_BOOKING: [CallbackQueryHandler(booking_confirmed, pattern="^conf_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("my_bookings", my_bookings))
    application.add_handler(MessageHandler(filters.Regex("^🍴 Menu$"), show_menu))
    application.add_handler(MessageHandler(filters.Regex("^📈 Owner Summary$"), owner_summary))
    application.add_handler(CallbackQueryHandler(cancel_booking_callback, pattern="^cancel_"))
    application.add_handler(conv_handler)

    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
