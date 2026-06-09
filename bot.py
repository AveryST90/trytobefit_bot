"""
FitCoach Bot — Telegram bot for fitness trainers
Manages clients, sessions, workout plans, and sends reminders.
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from db import Database
from config import BOT_TOKEN, REMINDER_HOURS, MAX_CLIENTS
from scheduler import setup_scheduler
from keyboards import (
    main_menu_keyboard, clients_menu_keyboard, schedule_menu_keyboard,
    workout_menu_keyboard, back_keyboard, confirm_keyboard,
    days_keyboard, time_keyboard, client_list_keyboard
)
from messages import *

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ── Conversation states ──────────────────────────────────────────────────────
(
    ADD_CLIENT_NAME, ADD_CLIENT_PHONE, ADD_CLIENT_NOTES,
    ADD_SESSION_CLIENT, ADD_SESSION_DATE, ADD_SESSION_TIME,
    ADD_SESSION_DURATION, ADD_SESSION_NOTES,
    ADD_PLAN_CLIENT, ADD_PLAN_TITLE, ADD_PLAN_CONTENT,
    CONFIRM_DELETE_CLIENT, CONFIRM_DELETE_SESSION,
) = range(13)


# ── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        WELCOME_MSG.format(name=user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


# ── Main menu callback ────────────────────────────────────────────────────────
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        MAIN_MENU_MSG,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════════
#  CLIENT MANAGEMENT
# ══════════════════════════════════════════════════════════════════

async def clients_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    count = len(clients)
    await query.edit_message_text(
        CLIENTS_MENU_MSG.format(count=count, max=MAX_CLIENTS),
        reply_markup=clients_menu_keyboard(),
        parse_mode="HTML"
    )


async def list_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    if not clients:
        await query.edit_message_text(
            NO_CLIENTS_MSG,
            reply_markup=clients_menu_keyboard(),
            parse_mode="HTML"
        )
        return
    text = "<b>👤 Client Roster</b>\n" + "─" * 28 + "\n\n"
    for i, c in enumerate(clients, 1):
        next_session = db.get_next_session_for_client(c["id"])
        ns_text = f"\n   <i>Next: {next_session}</i>" if next_session else ""
        text += f"<b>{i:02d}.</b> {c['name']}{ns_text}\n"
    await query.edit_message_text(
        text,
        reply_markup=clients_menu_keyboard(),
        parse_mode="HTML"
    )


# ── Add client flow ──────────────────────────────────────────────────────────
async def add_client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if len(db.get_all_clients()) >= MAX_CLIENTS:
        await query.edit_message_text(
            MAX_CLIENTS_MSG.format(max=MAX_CLIENTS),
            reply_markup=clients_menu_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    await query.edit_message_text(ADD_CLIENT_NAME_MSG, parse_mode="HTML")
    return ADD_CLIENT_NAME


async def add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_client"] = {"name": update.message.text.strip()}
    await update.message.reply_text(ADD_CLIENT_PHONE_MSG, parse_mode="HTML")
    return ADD_CLIENT_PHONE


async def add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_client"]["phone"] = update.message.text.strip()
    await update.message.reply_text(ADD_CLIENT_NOTES_MSG, parse_mode="HTML")
    return ADD_CLIENT_NOTES


async def add_client_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data["new_client"]
    data["notes"] = update.message.text.strip()
    client_id = db.add_client(data["name"], data["phone"], data["notes"])
    await update.message.reply_text(
        CLIENT_ADDED_MSG.format(name=data["name"], id=client_id),
        reply_markup=clients_menu_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ── Delete client ─────────────────────────────────────────────────────────────
async def delete_client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    if not clients:
        await query.edit_message_text(
            NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML"
        )
        return ConversationHandler.END
    await query.edit_message_text(
        "<b>🗑 Remove Client</b>\n\nSelect the client to remove:",
        reply_markup=client_list_keyboard(clients, prefix="del_client"),
        parse_mode="HTML"
    )
    return CONFIRM_DELETE_CLIENT


async def confirm_delete_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = db.get_client(client_id)
    if not client:
        await query.edit_message_text("Client not found.", reply_markup=clients_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    context.user_data["delete_client_id"] = client_id
    await query.edit_message_text(
        CONFIRM_DELETE_CLIENT_MSG.format(name=client["name"]),
        reply_markup=confirm_keyboard("confirm_del_client", "cancel_del_client"),
        parse_mode="HTML"
    )
    return CONFIRM_DELETE_CLIENT


async def execute_delete_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_del_client":
        client_id = context.user_data.get("delete_client_id")
        client = db.get_client(client_id)
        db.delete_client(client_id)
        await query.edit_message_text(
            CLIENT_DELETED_MSG.format(name=client["name"]),
            reply_markup=clients_menu_keyboard(),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            "Deletion cancelled.", reply_markup=clients_menu_keyboard(), parse_mode="HTML"
        )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
#  SCHEDULE MANAGEMENT
# ══════════════════════════════════════════════════════════════════

async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        SCHEDULE_MENU_MSG,
        reply_markup=schedule_menu_keyboard(),
        parse_mode="HTML"
    )


async def view_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = date.today()
    sessions = db.get_sessions_for_date(today)
    text = format_daily_schedule(today, sessions)
    await query.edit_message_text(text, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")


async def view_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_sessions = {}
    for i in range(7):
        d = monday + timedelta(days=i)
        week_sessions[d] = db.get_sessions_for_date(d)
    text = format_weekly_schedule(monday, week_sessions)
    await query.edit_message_text(text, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")


async def view_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = date.today()
    first_day = today.replace(day=1)
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    sessions = db.get_sessions_for_range(first_day, last_day)
    text = format_monthly_schedule(today, sessions)
    await query.edit_message_text(text, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")


# ── Add session flow ──────────────────────────────────────────────────────────
async def add_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    if not clients:
        await query.edit_message_text(
            NO_CLIENTS_FOR_SESSION_MSG,
            reply_markup=schedule_menu_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    await query.edit_message_text(
        "<b>📅 New Session</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients, prefix="sess_client"),
        parse_mode="HTML"
    )
    return ADD_SESSION_CLIENT


async def add_session_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    context.user_data["new_session"] = {"client_id": client_id}
    client = db.get_client(client_id)
    context.user_data["new_session"]["client_name"] = client["name"]
    await query.edit_message_text(
        f"<b>📅 New Session — {client['name']}</b>\n\nEnter the date:\n<code>Format: DD/MM/YYYY  (e.g. 25/06/2025)</code>",
        parse_mode="HTML"
    )
    return ADD_SESSION_DATE


async def add_session_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        session_date = datetime.strptime(text, "%d/%m/%Y").date()
        if session_date < date.today():
            await update.message.reply_text("⚠️ Date is in the past. Please enter a future date (DD/MM/YYYY):")
            return ADD_SESSION_DATE
        context.user_data["new_session"]["date"] = session_date
        await update.message.reply_text(
            f"<b>📅 Session — {context.user_data['new_session']['client_name']}</b>\n\nEnter the start time:\n<code>Format: HH:MM  (e.g. 09:30)</code>",
            parse_mode="HTML"
        )
        return ADD_SESSION_TIME
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use DD/MM/YYYY (e.g. 25/06/2025):")
        return ADD_SESSION_DATE


async def add_session_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        session_time = datetime.strptime(text, "%H:%M").time()
        context.user_data["new_session"]["time"] = session_time
        await update.message.reply_text(
            "Session duration in minutes:\n<code>e.g. 60</code>",
            parse_mode="HTML"
        )
        return ADD_SESSION_DURATION
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use HH:MM (e.g. 09:30):")
        return ADD_SESSION_TIME


async def add_session_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration = int(update.message.text.strip())
        if duration <= 0 or duration > 300:
            raise ValueError
        context.user_data["new_session"]["duration"] = duration
        await update.message.reply_text(
            "Session notes (type <code>skip</code> to leave blank):",
            parse_mode="HTML"
        )
        return ADD_SESSION_NOTES
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid duration in minutes (e.g. 60):")
        return ADD_SESSION_DURATION


async def add_session_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = context.user_data["new_session"]
    data["notes"] = "" if text.lower() == "skip" else text
    session_id = db.add_session(
        data["client_id"],
        data["date"],
        data["time"],
        data["duration"],
        data["notes"]
    )
    await update.message.reply_text(
        SESSION_ADDED_MSG.format(
            name=data["client_name"],
            date=data["date"].strftime("%A, %d %B %Y"),
            time=data["time"].strftime("%H:%M"),
            duration=data["duration"]
        ),
        reply_markup=schedule_menu_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ── Delete session ────────────────────────────────────────────────────────────
async def delete_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = date.today()
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await query.edit_message_text(
            "No upcoming sessions found.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML"
        )
        return ConversationHandler.END
    keyboard = []
    for s in sessions:
        label = f"{s['date']} {s['time']} — {s['client_name']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"del_sess:{s['id']}")])
    keyboard.append([InlineKeyboardButton("↩ Back", callback_data="schedule_menu")])
    await query.edit_message_text(
        "<b>🗑 Cancel Session</b>\n\nSelect session to remove:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return CONFIRM_DELETE_SESSION


async def confirm_delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session_id = int(query.data.split(":")[1])
    session = db.get_session(session_id)
    context.user_data["delete_session_id"] = session_id
    await query.edit_message_text(
        CONFIRM_DELETE_SESSION_MSG.format(
            name=session["client_name"],
            date=session["date"],
            time=session["time"]
        ),
        reply_markup=confirm_keyboard("confirm_del_sess", "cancel_del_sess"),
        parse_mode="HTML"
    )
    return CONFIRM_DELETE_SESSION


async def execute_delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_del_sess":
        session_id = context.user_data.get("delete_session_id")
        db.delete_session(session_id)
        await query.edit_message_text(
            "✅ Session removed from your schedule.",
            reply_markup=schedule_menu_keyboard(), parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            "Deletion cancelled.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML"
        )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
#  WORKOUT PLANS
# ══════════════════════════════════════════════════════════════════

async def workout_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        WORKOUT_MENU_MSG,
        reply_markup=workout_menu_keyboard(),
        parse_mode="HTML"
    )


async def list_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    plans_text = "<b>📋 Workout Plans</b>\n" + "─" * 28 + "\n\n"
    any_plan = False
    for c in clients:
        plans = db.get_plans_for_client(c["id"])
        if plans:
            any_plan = True
            plans_text += f"<b>👤 {c['name']}</b>\n"
            for p in plans:
                plans_text += f"  • {p['title']} <i>({p['created_at']})</i>\n"
            plans_text += "\n"
    if not any_plan:
        plans_text += "<i>No workout plans yet.</i>"
    await query.edit_message_text(plans_text, reply_markup=workout_menu_keyboard(), parse_mode="HTML")


async def add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    if not clients:
        await query.edit_message_text(
            NO_CLIENTS_MSG, reply_markup=workout_menu_keyboard(), parse_mode="HTML"
        )
        return ConversationHandler.END
    await query.edit_message_text(
        "<b>📋 New Workout Plan</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients, prefix="plan_client"),
        parse_mode="HTML"
    )
    return ADD_PLAN_CLIENT


async def add_plan_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = db.get_client(client_id)
    context.user_data["new_plan"] = {"client_id": client_id, "client_name": client["name"]}
    await query.edit_message_text(
        f"<b>📋 Plan for {client['name']}</b>\n\nEnter the plan title (e.g. \"Week 1 — Strength Foundation\"):",
        parse_mode="HTML"
    )
    return ADD_PLAN_TITLE


async def add_plan_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_plan"]["title"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>📋 Workout Plan Content</b>\n\nEnter the full workout plan. You can use line breaks for structure:\n\n<code>Day 1 — Push\nBench Press 4x8\nShoulder Press 3x10\n\nDay 2 — Pull\nDeadlift 4x5\nRows 3x12</code>",
        parse_mode="HTML"
    )
    return ADD_PLAN_CONTENT


async def add_plan_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data["new_plan"]
    data["content"] = update.message.text.strip()
    db.add_plan(data["client_id"], data["title"], data["content"])
    await update.message.reply_text(
        PLAN_ADDED_MSG.format(name=data["client_name"], title=data["title"]),
        reply_markup=workout_menu_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def view_client_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    clients = db.get_all_clients()
    clients_with_plans = [c for c in clients if db.get_plans_for_client(c["id"])]
    if not clients_with_plans:
        await query.edit_message_text(
            "No workout plans found.", reply_markup=workout_menu_keyboard(), parse_mode="HTML"
        )
        return
    await query.edit_message_text(
        "<b>📋 View Plan</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients_with_plans, prefix="view_plan"),
        parse_mode="HTML"
    )


async def show_client_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = int(query.data.split(":")[1])
    client = db.get_client(client_id)
    plans = db.get_plans_for_client(client_id)
    if not plans:
        await query.edit_message_text(
            f"No plans for {client['name']}.", reply_markup=workout_menu_keyboard(), parse_mode="HTML"
        )
        return
    text = f"<b>📋 {client['name']} — Workout Plans</b>\n" + "─" * 28 + "\n\n"
    for p in plans:
        text += f"<b>{p['title']}</b>  <i>{p['created_at']}</i>\n{p['content']}\n\n{'─'*20}\n\n"
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:3990] + "\n<i>... truncated</i>"
    await query.edit_message_text(text, reply_markup=workout_menu_keyboard(), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════
#  HELPERS / FORMATTERS
# ══════════════════════════════════════════════════════════════════

def format_daily_schedule(day: date, sessions: list) -> str:
    header = f"<b>📅 {day.strftime('%A, %d %B %Y')}</b>\n" + "─" * 28 + "\n\n"
    if not sessions:
        return header + "<i>No sessions scheduled.</i>"
    body = ""
    for s in sorted(sessions, key=lambda x: x["time"]):
        body += f"🕐 <b>{s['time']}</b>  {s['client_name']}  <i>({s['duration']} min)</i>\n"
        if s.get("notes"):
            body += f"   📝 {s['notes']}\n"
        body += "\n"
    return header + body


def format_weekly_schedule(monday: date, week_sessions: dict) -> str:
    text = f"<b>📆 Week of {monday.strftime('%d %B %Y')}</b>\n" + "─" * 28 + "\n\n"
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, (d, sessions) in enumerate(week_sessions.items()):
        marker = "▶" if d == date.today() else "  "
        text += f"{marker} <b>{day_names[i]} {d.strftime('%d/%m')}</b>\n"
        if sessions:
            for s in sorted(sessions, key=lambda x: x["time"]):
                text += f"    {s['time']} — {s['client_name']} ({s['duration']}m)\n"
        else:
            text += "    <i>Free</i>\n"
        text += "\n"
    return text


def format_monthly_schedule(today: date, sessions: list) -> str:
    month_name = today.strftime("%B %Y")
    text = f"<b>🗓 {month_name}</b>\n" + "─" * 28 + "\n\n"
    by_day: dict = {}
    for s in sessions:
        by_day.setdefault(s["date"], []).append(s)
    if not by_day:
        return text + "<i>No sessions this month.</i>"
    for d in sorted(by_day.keys()):
        day_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
        marker = "▶ " if day_obj == today else ""
        text += f"{marker}<b>{day_obj.strftime('%a %d')}</b>\n"
        for s in sorted(by_day[d], key=lambda x: x["time"]):
            text += f"  {s['time']} {s['client_name']} ({s['duration']}m)\n"
        text += "\n"
    total = sum(len(v) for v in by_day.values())
    text += f"<i>Total: {total} session{'s' if total != 1 else ''} this month</i>"
    return text


# ══════════════════════════════════════════════════════════════════
#  CANCEL / FALLBACK
# ══════════════════════════════════════════════════════════════════

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )
    return ConversationHandler.END


async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Unknown action.", show_alert=False)


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Conversation: add client ─────────────────────────────────
    add_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_client_start, pattern="^add_client$")],
        states={
            ADD_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_name)],
            ADD_CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_phone)],
            ADD_CLIENT_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Conversation: delete client ──────────────────────────────
    del_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_client_start, pattern="^delete_client$")],
        states={
            CONFIRM_DELETE_CLIENT: [
                CallbackQueryHandler(confirm_delete_client, pattern="^del_client:"),
                CallbackQueryHandler(execute_delete_client, pattern="^(confirm|cancel)_del_client$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Conversation: add session ────────────────────────────────
    add_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_session_start, pattern="^add_session$")],
        states={
            ADD_SESSION_CLIENT: [CallbackQueryHandler(add_session_client, pattern="^sess_client:")],
            ADD_SESSION_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_date)],
            ADD_SESSION_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_time)],
            ADD_SESSION_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_duration)],
            ADD_SESSION_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Conversation: delete session ─────────────────────────────
    del_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_session_start, pattern="^delete_session$")],
        states={
            CONFIRM_DELETE_SESSION: [
                CallbackQueryHandler(confirm_delete_session, pattern="^del_sess:"),
                CallbackQueryHandler(execute_delete_session, pattern="^(confirm|cancel)_del_sess$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Conversation: add plan ───────────────────────────────────
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_plan_start, pattern="^add_plan$")],
        states={
            ADD_PLAN_CLIENT: [CallbackQueryHandler(add_plan_client, pattern="^plan_client:")],
            ADD_PLAN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_title)],
            ADD_PLAN_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Register all handlers ────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_client_conv)
    app.add_handler(del_client_conv)
    app.add_handler(add_session_conv)
    app.add_handler(del_session_conv)
    app.add_handler(add_plan_conv)

    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(clients_menu, pattern="^clients_menu$"))
    app.add_handler(CallbackQueryHandler(list_clients, pattern="^list_clients$"))
    app.add_handler(CallbackQueryHandler(schedule_menu, pattern="^schedule_menu$"))
    app.add_handler(CallbackQueryHandler(view_today, pattern="^view_today$"))
    app.add_handler(CallbackQueryHandler(view_weekly, pattern="^view_weekly$"))
    app.add_handler(CallbackQueryHandler(view_monthly, pattern="^view_monthly$"))
    app.add_handler(CallbackQueryHandler(workout_menu, pattern="^workout_menu$"))
    app.add_handler(CallbackQueryHandler(list_plans, pattern="^list_plans$"))
    app.add_handler(CallbackQueryHandler(view_client_plan, pattern="^view_client_plan$"))
    app.add_handler(CallbackQueryHandler(show_client_plans, pattern="^view_plan:"))
    app.add_handler(CallbackQueryHandler(unknown_callback))

    # ── Reminder scheduler ───────────────────────────────────────
    setup_scheduler(app, db)

    logger.info("FitCoach Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
