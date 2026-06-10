"""
╔══════════════════════════════════════════════════════════════════╗
║                        FITCOACH BOT                             ║
║              Telegram Bot for Fitness Trainers                  ║
║                                                                  ║
║  Features:                                                       ║
║  • Manage up to 50 clients (add / remove / view roster)         ║
║  • Schedule sessions with date, time & duration                 ║
║  • Daily / Weekly / Monthly schedule views                      ║
║  • Workout plan management per client                           ║
║  • Automatic 1h & 2h session reminders                         ║
║                                                                  ║
║  Deploy:  Railway · Docker · any Python 3.10+ host              ║
║  Config:  Set BOT_TOKEN env var (or edit CONFIG below)          ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════
#  STANDARD LIBRARY
# ═══════════════════════════════════════════════════════════════════
import os
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════════
#  THIRD-PARTY  (pip install python-telegram-bot)
# ═══════════════════════════════════════════════════════════════════
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ═══════════════════════════════════════════════════════════════════
#  ① CONFIG  — edit here or set environment variables a
# ═══════════════════════════════════════════════════════════════════

BOT_TOKEN    = os.getenv("BOT_TOKEN", "8728837807:AAFpE51RGvnG0LzWfZyt_KQO6dctj9Tssf4")
REMINDER_HOURS = [1, 2]   # send reminders 2h and 1h before each session
MAX_CLIENTS  = 50
DB_PATH      = Path(os.getenv("DB_PATH", "fitcoach.db"))

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  ② DATABASE  — SQLite, auto-created on first run
# ═══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS clients (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                phone      TEXT,
                notes      TEXT,
                created_at TEXT    DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                session_date TEXT    NOT NULL,
                session_time TEXT    NOT NULL,
                duration     INTEGER NOT NULL DEFAULT 60,
                notes        TEXT,
                reminded_1h  INTEGER DEFAULT 0,
                reminded_2h  INTEGER DEFAULT 0,
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workout_plans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                title      TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                created_at TEXT    DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS trainer_chat (
                id      INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL
            );
        """)
        self.conn.commit()

    # ── Trainer chat ──────────────────────────────────────────────
    def set_trainer_chat(self, chat_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trainer_chat")
        cur.execute("INSERT INTO trainer_chat (id, chat_id) VALUES (1, ?)", (chat_id,))
        self.conn.commit()

    def get_trainer_chat(self) -> Optional[int]:
        row = self.conn.execute(
            "SELECT chat_id FROM trainer_chat WHERE id=1"
        ).fetchone()
        return row["chat_id"] if row else None

    # ── Clients ───────────────────────────────────────────────────
    def get_all_clients(self) -> list:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM clients ORDER BY name"
        ).fetchall()]

    def get_client(self, client_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM clients WHERE id=?", (client_id,)
        ).fetchone()
        return dict(row) if row else None

    def add_client(self, name: str, phone: str, notes: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO clients (name, phone, notes) VALUES (?, ?, ?)",
            (name, phone, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_client(self, client_id: int):
        self.conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
        self.conn.commit()

    def get_next_session_for_client(self, client_id: int) -> Optional[str]:
        today = date.today().isoformat()
        row = self.conn.execute(
            """SELECT session_date, session_time FROM sessions
               WHERE client_id=? AND session_date >= ?
               ORDER BY session_date, session_time LIMIT 1""",
            (client_id, today),
        ).fetchone()
        return f"{row['session_date']}  {row['session_time']}" if row else None

    # ── Sessions ──────────────────────────────────────────────────
    def add_session(self, client_id: int, session_date: date,
                    session_time, duration: int, notes: str) -> int:
        if hasattr(session_time, "strftime"):
            time_str = session_time.strftime("%H:%M")
        else:
            time_str = str(session_time)
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO sessions
               (client_id, session_date, session_time, duration, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (client_id, session_date.isoformat(), time_str, duration, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_session(self, session_id: int) -> Optional[dict]:
        row = self.conn.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.id=?""",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_sessions_for_date(self, day: date) -> list:
        rows = self.conn.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date=?
               ORDER BY s.session_time""",
            (day.isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_range(self, start: date, end: date) -> list:
        rows = self.conn.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date BETWEEN ? AND ?
               ORDER BY s.session_date, s.session_time""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming_sessions(self, limit: int = 20) -> list:
        today = date.today().isoformat()
        rows = self.conn.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date >= ?
               ORDER BY s.session_date, s.session_time
               LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: int):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.conn.commit()

    def get_sessions_needing_reminder(self, hours_before: int) -> list:
        now    = datetime.now()
        target = now + timedelta(hours=hours_before)
        col    = f"reminded_{hours_before}h"
        rows   = self.conn.execute(
            f"""SELECT s.*, c.name AS client_name FROM sessions s
                JOIN clients c ON c.id = s.client_id
                WHERE s.{col} = 0
                  AND s.session_date = ?
                  AND s.session_time BETWEEN ? AND ?
                ORDER BY s.session_time""",
            (
                target.date().isoformat(),
                target.strftime("%H:%M"),
                (target + timedelta(minutes=1)).strftime("%H:%M"),
            ),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminded(self, session_id: int, hours_before: int):
        col = f"reminded_{hours_before}h"
        self.conn.execute(
            f"UPDATE sessions SET {col}=1 WHERE id=?", (session_id,)
        )
        self.conn.commit()

    # ── Workout plans ─────────────────────────────────────────────
    def add_plan(self, client_id: int, title: str, content: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO workout_plans (client_id, title, content) VALUES (?, ?, ?)",
            (client_id, title, content),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_plans_for_client(self, client_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM workout_plans WHERE client_id=? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════
#  ③ MESSAGES  — all bot copy in one place
# ═══════════════════════════════════════════════════════════════════

WELCOME_MSG = (
    "💪 <b>FitCoach Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Welcome back, <b>{name}</b>.\n\n"
    "Manage your clients, schedule training sessions, assign workout plans, "
    "and receive timely reminders — all in one place.\n\n"
    "Select an option below to get started."
)
MAIN_MENU_MSG = (
    "🏋️ <b>FitCoach Bot — Main Menu</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "What would you like to manage today?"
)
CLIENTS_MENU_MSG = (
    "👤 <b>Client Management</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Active clients: <b>{count} / {max}</b>\n\n"
    "Add or remove clients, or view your full roster."
)
NO_CLIENTS_MSG      = "👤 <b>No clients yet.</b>\n\nAdd your first client to get started."
MAX_CLIENTS_MSG     = "⚠️ <b>Client limit reached ({max} clients).</b>\n\nRemove an existing client before adding a new one."
ADD_CLIENT_NAME_MSG = "➕ <b>New Client</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nEnter the client's full name:"
ADD_CLIENT_PHONE_MSG= "Enter the client's phone number:\n<i>(Type <code>skip</code> to leave blank)</i>"
ADD_CLIENT_NOTES_MSG= "Any notes for this client?\n<i>e.g. injuries, goals, preferences\n(Type <code>skip</code> to leave blank)</i>"
CLIENT_ADDED_MSG    = "✅ <b>{name}</b> added to your roster.\n<i>Client ID: {id}</i>"
CONFIRM_DELETE_CLIENT_MSG = (
    "⚠️ <b>Remove Client</b>\n\n"
    "Remove <b>{name}</b> from your roster?\n\n"
    "<i>All sessions and workout plans for this client will also be deleted. "
    "This cannot be undone.</i>"
)
CLIENT_DELETED_MSG  = "✅ <b>{name}</b> has been removed from your roster."
SCHEDULE_MENU_MSG   = (
    "📅 <b>Schedule</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "View your daily, weekly, or monthly training schedule, "
    "or add / cancel sessions."
)
NO_CLIENTS_FOR_SESSION_MSG = (
    "⚠️ No clients on your roster yet.\n\n"
    "Add at least one client before scheduling a session."
)
SESSION_ADDED_MSG = (
    "✅ <b>Session Scheduled</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "👤 Client   : <b>{name}</b>\n"
    "📅 Date     : {date}\n"
    "🕐 Time     : {time}\n"
    "⏱ Duration : {duration} min\n\n"
    "<i>You'll receive a reminder 1 h and 2 h before this session.</i>"
)
CONFIRM_DELETE_SESSION_MSG = (
    "⚠️ <b>Cancel Session</b>\n\n"
    "Cancel the session with <b>{name}</b>\n"
    "on {date} at {time}?\n\n"
    "<i>This action cannot be undone.</i>"
)
REMINDER_MSG = (
    "🔔 <b>Session Reminder</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "⏰ <b>{hours} hour{plural}</b> until your session with:\n\n"
    "👤 <b>{name}</b>\n"
    "🕐 {time}  •  {duration} min"
)
WORKOUT_MENU_MSG = (
    "📋 <b>Workout Plans</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Create and manage personalised workout plans for each client."
)
PLAN_ADDED_MSG = (
    "✅ <b>Workout Plan Saved</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "👤 Client : <b>{name}</b>\n"
    "📋 Plan   : {title}"
)


# ═══════════════════════════════════════════════════════════════════
#  ④ KEYBOARDS  — inline button builders
# ═══════════════════════════════════════════════════════════════════

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤  Clients",       callback_data="clients_menu"),
            InlineKeyboardButton("📅  Schedule",      callback_data="schedule_menu"),
        ],
        [InlineKeyboardButton("📋  Workout Plans",   callback_data="workout_menu")],
    ])

def clients_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕  Add Client",    callback_data="add_client"),
            InlineKeyboardButton("🗑  Remove Client", callback_data="delete_client"),
        ],
        [InlineKeyboardButton("📋  View All Clients", callback_data="list_clients")],
        [InlineKeyboardButton("↩  Main Menu",         callback_data="main_menu")],
    ])

def schedule_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅  Today",       callback_data="view_today"),
            InlineKeyboardButton("📆  This Week",   callback_data="view_weekly"),
            InlineKeyboardButton("🗓  This Month",  callback_data="view_monthly"),
        ],
        [
            InlineKeyboardButton("➕  Add Session",    callback_data="add_session"),
            InlineKeyboardButton("🗑  Cancel Session", callback_data="delete_session"),
        ],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])

def workout_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕  New Plan",         callback_data="add_plan"),
            InlineKeyboardButton("📋  All Plans",        callback_data="list_plans"),
        ],
        [InlineKeyboardButton("👤  Plans by Client",     callback_data="view_client_plan")],
        [InlineKeyboardButton("↩  Main Menu",            callback_data="main_menu")],
    ])

def confirm_keyboard(confirm_data: str, cancel_data: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅  Confirm", callback_data=confirm_data),
            InlineKeyboardButton("✖  Cancel",  callback_data=cancel_data),
        ]
    ])

def client_list_keyboard(clients: list, prefix: str):
    rows = [
        [InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")]
        for c in clients
    ]
    rows.append([InlineKeyboardButton("✖  Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════════════════════════════
#  ⑤ SCHEDULER  — reminder loop (runs every 60 s inside the bot)
# ═══════════════════════════════════════════════════════════════════

async def reminder_loop(app: Application, db: Database):
    """Background task — checks every minute for upcoming sessions."""
    while True:
        try:
            chat_id = db.get_trainer_chat()
            if chat_id:
                for hours in REMINDER_HOURS:
                    for session in db.get_sessions_needing_reminder(hours):
                        plural = "" if hours == 1 else "s"
                        msg = REMINDER_MSG.format(
                            hours=hours,
                            plural=plural,
                            name=session["client_name"],
                            time=session["session_time"],
                            duration=session["duration"],
                        )
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode="HTML",
                        )
                        db.mark_reminded(session["id"], hours)
        except Exception as exc:
            logger.error("Reminder error: %s", exc)
        await asyncio.sleep(60)


def setup_scheduler(app: Application, db: Database):
    async def _start_loop(application: Application):
        asyncio.create_task(reminder_loop(application, db))
    app.post_init = _start_loop


# ═══════════════════════════════════════════════════════════════════
#  ⑥ CONVERSATION STATES
# ═══════════════════════════════════════════════════════════════════

(
    ADD_CLIENT_NAME, ADD_CLIENT_PHONE, ADD_CLIENT_NOTES,
    ADD_SESSION_CLIENT, ADD_SESSION_DATE, ADD_SESSION_TIME,
    ADD_SESSION_DURATION, ADD_SESSION_NOTES,
    ADD_PLAN_CLIENT, ADD_PLAN_TITLE, ADD_PLAN_CONTENT,
    CONFIRM_DELETE_CLIENT, CONFIRM_DELETE_SESSION,
) = range(13)


# ═══════════════════════════════════════════════════════════════════
#  ⑦ SCHEDULE FORMATTERS
# ═══════════════════════════════════════════════════════════════════

def fmt_daily(day: date, sessions: list) -> str:
    h = f"<b>📅 {day.strftime('%A, %d %B %Y')}</b>\n" + "─" * 28 + "\n\n"
    if not sessions:
        return h + "<i>No sessions scheduled.</i>"
    body = ""
    for s in sorted(sessions, key=lambda x: x["session_time"]):
        body += f"🕐 <b>{s['session_time']}</b>  {s['client_name']}  <i>({s['duration']} min)</i>\n"
        if s.get("notes"):
            body += f"   📝 {s['notes']}\n"
        body += "\n"
    return h + body

def fmt_weekly(monday: date, week: dict) -> str:
    txt = f"<b>📆 Week of {monday.strftime('%d %B %Y')}</b>\n" + "─" * 28 + "\n\n"
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, (d, sessions) in enumerate(week.items()):
        marker = "▶" if d == date.today() else "  "
        txt += f"{marker} <b>{day_names[i]} {d.strftime('%d/%m')}</b>\n"
        if sessions:
            for s in sorted(sessions, key=lambda x: x["session_time"]):
                txt += f"    {s['session_time']} — {s['client_name']} ({s['duration']}m)\n"
        else:
            txt += "    <i>Free</i>\n"
        txt += "\n"
    return txt

def fmt_monthly(today: date, sessions: list) -> str:
    txt = f"<b>🗓 {today.strftime('%B %Y')}</b>\n" + "─" * 28 + "\n\n"
    by_day: dict = {}
    for s in sessions:
        by_day.setdefault(s["session_date"], []).append(s)
    if not by_day:
        return txt + "<i>No sessions this month.</i>"
    for d in sorted(by_day):
        day_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
        marker  = "▶ " if day_obj == today else ""
        txt    += f"{marker}<b>{day_obj.strftime('%a %d')}</b>\n"
        for s in sorted(by_day[d], key=lambda x: x["session_time"]):
            txt += f"  {s['session_time']} {s['client_name']} ({s['duration']}m)\n"
        txt += "\n"
    total = sum(len(v) for v in by_day.values())
    txt  += f"<i>Total: {total} session{'s' if total != 1 else ''} this month</i>"
    return txt


# ═══════════════════════════════════════════════════════════════════
#  ⑧ HANDLERS
# ═══════════════════════════════════════════════════════════════════

db = Database()


# ── /start ────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_trainer_chat(update.effective_chat.id)
    await update.message.reply_text(
        WELCOME_MSG.format(name=update.effective_user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

async def cmd_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(MAIN_MENU_MSG, reply_markup=main_menu_keyboard(), parse_mode="HTML")


# ── Clients ───────────────────────────────────────────────────────
async def cmd_clients_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    count = len(db.get_all_clients())
    await q.edit_message_text(
        CLIENTS_MENU_MSG.format(count=count, max=MAX_CLIENTS),
        reply_markup=clients_menu_keyboard(), parse_mode="HTML",
    )

async def cmd_list_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML")
        return
    txt = "<b>👤 Client Roster</b>\n" + "─" * 28 + "\n\n"
    for i, c in enumerate(clients, 1):
        ns = db.get_next_session_for_client(c["id"])
        txt += f"<b>{i:02d}.</b> {c['name']}"
        if ns:
            txt += f"\n   <i>Next: {ns}</i>"
        txt += "\n"
    await q.edit_message_text(txt, reply_markup=clients_menu_keyboard(), parse_mode="HTML")

# add client conversation
async def add_client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if len(db.get_all_clients()) >= MAX_CLIENTS:
        await q.edit_message_text(MAX_CLIENTS_MSG.format(max=MAX_CLIENTS), reply_markup=clients_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(ADD_CLIENT_NAME_MSG, parse_mode="HTML")
    return ADD_CLIENT_NAME

async def add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nc"] = {"name": update.message.text.strip()}
    await update.message.reply_text(ADD_CLIENT_PHONE_MSG, parse_mode="HTML")
    return ADD_CLIENT_PHONE

async def add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nc"]["phone"] = update.message.text.strip()
    await update.message.reply_text(ADD_CLIENT_NOTES_MSG, parse_mode="HTML")
    return ADD_CLIENT_NOTES

async def add_client_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["nc"]
    d["notes"] = "" if update.message.text.strip().lower() == "skip" else update.message.text.strip()
    cid = db.add_client(d["name"], d["phone"], d["notes"])
    await update.message.reply_text(
        CLIENT_ADDED_MSG.format(name=d["name"], id=cid),
        reply_markup=clients_menu_keyboard(), parse_mode="HTML",
    )
    return ConversationHandler.END

# delete client conversation
async def delete_client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(
        "<b>🗑 Remove Client</b>\n\nSelect the client to remove:",
        reply_markup=client_list_keyboard(clients, "del_client"), parse_mode="HTML",
    )
    return CONFIRM_DELETE_CLIENT

async def confirm_delete_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1])
    client = db.get_client(cid)
    if not client:
        await q.edit_message_text("Client not found.", reply_markup=clients_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    context.user_data["del_cid"] = cid
    await q.edit_message_text(
        CONFIRM_DELETE_CLIENT_MSG.format(name=client["name"]),
        reply_markup=confirm_keyboard("confirm_del_client", "cancel_del_client"), parse_mode="HTML",
    )
    return CONFIRM_DELETE_CLIENT

async def execute_delete_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "confirm_del_client":
        cid = context.user_data.get("del_cid")
        c   = db.get_client(cid)
        db.delete_client(cid)
        await q.edit_message_text(CLIENT_DELETED_MSG.format(name=c["name"]), reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    else:
        await q.edit_message_text("Deletion cancelled.", reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END


# ── Schedule ──────────────────────────────────────────────────────
async def cmd_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(SCHEDULE_MENU_MSG, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    today = date.today()
    await q.edit_message_text(fmt_daily(today, db.get_sessions_for_date(today)), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    week   = {monday + timedelta(days=i): db.get_sessions_for_date(monday + timedelta(days=i)) for i in range(7)}
    await q.edit_message_text(fmt_weekly(monday, week), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    today     = date.today()
    first_day = today.replace(day=1)
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    sessions = db.get_sessions_for_range(first_day, last_day)
    await q.edit_message_text(fmt_monthly(today, sessions), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

# add session conversation
async def add_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_FOR_SESSION_MSG, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(
        "<b>📅 New Session</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients, "sess_client"), parse_mode="HTML",
    )
    return ADD_SESSION_CLIENT

async def add_session_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid    = int(q.data.split(":")[1])
    client = db.get_client(cid)
    context.user_data["ns"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(
        f"<b>📅 New Session — {client['name']}</b>\n\nEnter the date:\n<code>Format: DD/MM/YYYY  (e.g. 25/06/2025)</code>",
        parse_mode="HTML",
    )
    return ADD_SESSION_DATE

async def add_session_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        d = datetime.strptime(txt, "%d/%m/%Y").date()
        if d < date.today():
            await update.message.reply_text("⚠️ Date is in the past. Enter a future date (DD/MM/YYYY):")
            return ADD_SESSION_DATE
        context.user_data["ns"]["date"] = d
        await update.message.reply_text(
            f"<b>📅 Session — {context.user_data['ns']['client_name']}</b>\n\nEnter the start time:\n<code>Format: HH:MM  (e.g. 09:30)</code>",
            parse_mode="HTML",
        )
        return ADD_SESSION_TIME
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use DD/MM/YYYY:")
        return ADD_SESSION_DATE

async def add_session_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        t = datetime.strptime(txt, "%H:%M").time()
        context.user_data["ns"]["time"] = t
        await update.message.reply_text("Session duration in minutes:\n<code>e.g. 60</code>", parse_mode="HTML")
        return ADD_SESSION_DURATION
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use HH:MM (e.g. 09:30):")
        return ADD_SESSION_TIME

async def add_session_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dur = int(update.message.text.strip())
        if not (1 <= dur <= 300):
            raise ValueError
        context.user_data["ns"]["duration"] = dur
        await update.message.reply_text("Session notes (type <code>skip</code> to leave blank):", parse_mode="HTML")
        return ADD_SESSION_NOTES
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid number of minutes (e.g. 60):")
        return ADD_SESSION_DURATION

async def add_session_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    d   = context.user_data["ns"]
    d["notes"] = "" if txt.lower() == "skip" else txt
    db.add_session(d["client_id"], d["date"], d["time"], d["duration"], d["notes"])
    await update.message.reply_text(
        SESSION_ADDED_MSG.format(
            name=d["client_name"],
            date=d["date"].strftime("%A, %d %B %Y"),
            time=d["time"].strftime("%H:%M"),
            duration=d["duration"],
        ),
        reply_markup=schedule_menu_keyboard(), parse_mode="HTML",
    )
    return ConversationHandler.END

# delete session conversation
async def delete_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await q.edit_message_text("No upcoming sessions found.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    kb = [
        [InlineKeyboardButton(
            f"{s['session_date']}  {s['session_time']} — {s['client_name']}",
            callback_data=f"del_sess:{s['id']}"
        )]
        for s in sessions
    ]
    kb.append([InlineKeyboardButton("↩ Back", callback_data="schedule_menu")])
    await q.edit_message_text(
        "<b>🗑 Cancel Session</b>\n\nSelect the session to remove:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML",
    )
    return CONFIRM_DELETE_SESSION

async def confirm_delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sid     = int(q.data.split(":")[1])
    session = db.get_session(sid)
    context.user_data["del_sid"] = sid
    await q.edit_message_text(
        CONFIRM_DELETE_SESSION_MSG.format(
            name=session["client_name"],
            date=session["session_date"],
            time=session["session_time"],
        ),
        reply_markup=confirm_keyboard("confirm_del_sess", "cancel_del_sess"), parse_mode="HTML",
    )
    return CONFIRM_DELETE_SESSION

async def execute_delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "confirm_del_sess":
        db.delete_session(context.user_data.get("del_sid"))
        await q.edit_message_text("✅ Session removed from your schedule.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
    else:
        await q.edit_message_text("Deletion cancelled.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END


# ── Workout plans ─────────────────────────────────────────────────
async def cmd_workout_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(WORKOUT_MENU_MSG, reply_markup=workout_menu_keyboard(), parse_mode="HTML")

async def cmd_list_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    txt, any_plan = "<b>📋 Workout Plans</b>\n" + "─" * 28 + "\n\n", False
    for c in clients:
        plans = db.get_plans_for_client(c["id"])
        if plans:
            any_plan = True
            txt += f"<b>👤 {c['name']}</b>\n"
            for p in plans:
                txt += f"  • {p['title']}  <i>({p['created_at']})</i>\n"
            txt += "\n"
    if not any_plan:
        txt += "<i>No workout plans yet.</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(), parse_mode="HTML")

async def add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=workout_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(
        "<b>📋 New Workout Plan</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients, "plan_client"), parse_mode="HTML",
    )
    return ADD_PLAN_CLIENT

async def add_plan_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid    = int(q.data.split(":")[1])
    client = db.get_client(cid)
    context.user_data["np"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(
        f"<b>📋 Plan for {client['name']}</b>\n\nEnter the plan title:\n<i>e.g. Week 1 — Strength Foundation</i>",
        parse_mode="HTML",
    )
    return ADD_PLAN_TITLE

async def add_plan_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np"]["title"] = update.message.text.strip()
    await update.message.reply_text(
        "<b>📋 Workout Plan Content</b>\n\nEnter the full workout plan.\nYou can use line breaks for structure:\n\n"
        "<code>Day 1 — Push\nBench Press 4×8\nShoulder Press 3×10\n\nDay 2 — Pull\nDeadlift 4×5\nRows 3×12</code>",
        parse_mode="HTML",
    )
    return ADD_PLAN_CONTENT

async def add_plan_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["np"]
    d["content"] = update.message.text.strip()
    db.add_plan(d["client_id"], d["title"], d["content"])
    await update.message.reply_text(
        PLAN_ADDED_MSG.format(name=d["client_name"], title=d["title"]),
        reply_markup=workout_menu_keyboard(), parse_mode="HTML",
    )
    return ConversationHandler.END

async def cmd_view_client_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    clients = [c for c in db.get_all_clients() if db.get_plans_for_client(c["id"])]
    if not clients:
        await q.edit_message_text("No workout plans found.", reply_markup=workout_menu_keyboard(), parse_mode="HTML")
        return
    await q.edit_message_text(
        "<b>📋 View Plan</b>\n\nSelect a client:",
        reply_markup=client_list_keyboard(clients, "view_plan"), parse_mode="HTML",
    )

async def cmd_show_client_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid    = int(q.data.split(":")[1])
    client = db.get_client(cid)
    plans  = db.get_plans_for_client(cid)
    if not plans:
        await q.edit_message_text(f"No plans for {client['name']}.", reply_markup=workout_menu_keyboard(), parse_mode="HTML")
        return
    txt = f"<b>📋 {client['name']} — Workout Plans</b>\n" + "─" * 28 + "\n\n"
    for p in plans:
        txt += f"<b>{p['title']}</b>  <i>{p['created_at']}</i>\n{p['content']}\n\n" + "─" * 20 + "\n\n"
    if len(txt) > 4000:
        txt = txt[:3990] + "\n<i>… truncated</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(), parse_mode="HTML")


# ── Fallback ──────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=main_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Unknown action.", show_alert=False)


# ═══════════════════════════════════════════════════════════════════
#  ⑨ MAIN  — wire everything together
# ═══════════════════════════════════════════════════════════════════

def main():
    pass

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Conversations ──────────────────────────────────────────────
    add_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_client_start, pattern="^add_client$")],
        states={
            ADD_CLIENT_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_name)],
            ADD_CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_phone)],
            ADD_CLIENT_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
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
    add_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_session_start, pattern="^add_session$")],
        states={
            ADD_SESSION_CLIENT:   [CallbackQueryHandler(add_session_client, pattern="^sess_client:")],
            ADD_SESSION_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_date)],
            ADD_SESSION_TIME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_time)],
            ADD_SESSION_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_duration)],
            ADD_SESSION_NOTES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
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
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_plan_start, pattern="^add_plan$")],
        states={
            ADD_PLAN_CLIENT:  [CallbackQueryHandler(add_plan_client, pattern="^plan_client:")],
            ADD_PLAN_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_title)],
            ADD_PLAN_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plan_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Commands ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))

    # ── Conversations ──────────────────────────────────────────────
    app.add_handler(add_client_conv)
    app.add_handler(del_client_conv)
    app.add_handler(add_session_conv)
    app.add_handler(del_session_conv)
    app.add_handler(add_plan_conv)

    # ── Callback buttons ───────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(cmd_main_menu,        pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_clients_menu,     pattern="^clients_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_clients,     pattern="^list_clients$"))
    app.add_handler(CallbackQueryHandler(cmd_schedule_menu,    pattern="^schedule_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_view_today,       pattern="^view_today$"))
    app.add_handler(CallbackQueryHandler(cmd_view_weekly,      pattern="^view_weekly$"))
    app.add_handler(CallbackQueryHandler(cmd_view_monthly,     pattern="^view_monthly$"))
    app.add_handler(CallbackQueryHandler(cmd_workout_menu,     pattern="^workout_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_plans,       pattern="^list_plans$"))
    app.add_handler(CallbackQueryHandler(cmd_view_client_plan, pattern="^view_client_plan$"))
    app.add_handler(CallbackQueryHandler(cmd_show_client_plans,pattern="^view_plan:"))
    app.add_handler(CallbackQueryHandler(unknown_callback))

    # ── Reminder scheduler ─────────────────────────────────────────
    setup_scheduler(app, db)

    logger.info("🏋️  FitCoach Bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
