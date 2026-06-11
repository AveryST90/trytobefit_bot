"""
╔══════════════════════════════════════════════════════════════════╗
║                        FITCOACH BOT  v2                         ║
║              Telegram Bot for Fitness Trainers                  ║
║                                                                  ║
║  NEW in v2:                                                      ║
║  • View All Clients shows phone + notes                         ║
║  • Edit existing client (name / phone / notes)                  ║
║  • Delete client — fully functional                             ║
║  • Client history (added + deleted) with per-entry delete       ║
║  • Edit existing session (date / time / duration / notes)       ║
║  • View All Sessions with full details including notes          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, logging, sqlite3, asyncio
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)

BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
REMINDER_HOURS = [1, 2]
MAX_CLIENTS    = 50
DB_PATH        = Path(os.getenv("DB_PATH", "fitcoach.db"))

logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                phone TEXT, notes TEXT, created_at TEXT DEFAULT (date('now'))
            );
            CREATE TABLE IF NOT EXISTS client_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
                client_name TEXT NOT NULL, phone TEXT, notes TEXT,
                action_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                session_date TEXT NOT NULL, session_time TEXT NOT NULL,
                duration INTEGER NOT NULL DEFAULT 60, notes TEXT,
                reminded_1h INTEGER DEFAULT 0, reminded_2h INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS workout_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                title TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT DEFAULT (date('now'))
            );
            CREATE TABLE IF NOT EXISTS trainer_chat (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL);
        """)
        self.conn.commit()

    def set_trainer_chat(self, chat_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trainer_chat")
        cur.execute("INSERT INTO trainer_chat (id, chat_id) VALUES (1, ?)", (chat_id,))
        self.conn.commit()

    def get_trainer_chat(self):
        row = self.conn.execute("SELECT chat_id FROM trainer_chat WHERE id=1").fetchone()
        return row["chat_id"] if row else None

    def get_all_clients(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM clients ORDER BY name").fetchall()]

    def get_client(self, cid):
        row = self.conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        return dict(row) if row else None

    def add_client(self, name, phone, notes):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, phone, notes) VALUES (?, ?, ?)", (name, phone, notes))
        self.conn.commit()
        self._log_history("ADDED", name, phone, notes)
        return cur.lastrowid

    def update_client(self, cid, name, phone, notes):
        self.conn.execute("UPDATE clients SET name=?, phone=?, notes=? WHERE id=?", (name, phone, notes, cid))
        self.conn.commit()

    def delete_client(self, cid):
        c = self.get_client(cid)
        if c:
            self._log_history("DELETED", c["name"], c.get("phone",""), c.get("notes",""))
        self.conn.execute("DELETE FROM clients WHERE id=?", (cid,))
        self.conn.commit()

    def get_next_session_for_client(self, cid):
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT session_date, session_time FROM sessions WHERE client_id=? AND session_date >= ? ORDER BY session_date, session_time LIMIT 1",
            (cid, today)).fetchone()
        return f"{row['session_date']}  {row['session_time']}" if row else None

    def _log_history(self, action, name, phone, notes):
        self.conn.execute("INSERT INTO client_history (action, client_name, phone, notes) VALUES (?, ?, ?, ?)",
                          (action, name, phone or "", notes or ""))
        self.conn.commit()

    def get_history(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM client_history ORDER BY action_at DESC").fetchall()]

    def delete_history_entry(self, entry_id):
        self.conn.execute("DELETE FROM client_history WHERE id=?", (entry_id,))
        self.conn.commit()

    def add_session(self, client_id, session_date, session_time, duration, notes):
        time_str = session_time.strftime("%H:%M") if hasattr(session_time, "strftime") else str(session_time)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sessions (client_id, session_date, session_time, duration, notes) VALUES (?, ?, ?, ?, ?)",
                    (client_id, session_date.isoformat(), time_str, duration, notes))
        self.conn.commit()
        return cur.lastrowid

    def update_session(self, sid, session_date, session_time, duration, notes):
        time_str = session_time.strftime("%H:%M") if hasattr(session_time, "strftime") else str(session_time)
        self.conn.execute("UPDATE sessions SET session_date=?, session_time=?, duration=?, notes=?, reminded_1h=0, reminded_2h=0 WHERE id=?",
                          (session_date.isoformat(), time_str, duration, notes, sid))
        self.conn.commit()

    def get_session(self, sid):
        row = self.conn.execute(
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id WHERE s.id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def get_sessions_for_date(self, day):
        rows = self.conn.execute(
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id WHERE s.session_date=? ORDER BY s.session_time",
            (day.isoformat(),)).fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_range(self, start, end):
        rows = self.conn.execute(
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id WHERE s.session_date BETWEEN ? AND ? ORDER BY s.session_date, s.session_time",
            (start.isoformat(), end.isoformat())).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming_sessions(self, limit=20):
        today = date.today().isoformat()
        rows = self.conn.execute(
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id WHERE s.session_date >= ? ORDER BY s.session_date, s.session_time LIMIT ?",
            (today, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_all_sessions(self, limit=50):
        rows = self.conn.execute(
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id ORDER BY s.session_date DESC, s.session_time DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, sid):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.conn.commit()

    def get_sessions_needing_reminder(self, hours_before):
        now = datetime.now()
        target = now + timedelta(hours=hours_before)
        col = f"reminded_{hours_before}h"
        rows = self.conn.execute(
            f"SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id WHERE s.{col}=0 AND s.session_date=? AND s.session_time BETWEEN ? AND ? ORDER BY s.session_time",
            (target.date().isoformat(), target.strftime("%H:%M"), (target + timedelta(minutes=1)).strftime("%H:%M"))).fetchall()
        return [dict(r) for r in rows]

    def mark_reminded(self, sid, hours_before):
        col = f"reminded_{hours_before}h"
        self.conn.execute(f"UPDATE sessions SET {col}=1 WHERE id=?", (sid,))
        self.conn.commit()

    def add_plan(self, client_id, title, content):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO workout_plans (client_id, title, content) VALUES (?, ?, ?)", (client_id, title, content))
        self.conn.commit()
        return cur.lastrowid

    def get_plans_for_client(self, client_id):
        rows = self.conn.execute("SELECT * FROM workout_plans WHERE client_id=? ORDER BY created_at DESC", (client_id,)).fetchall()
        return [dict(r) for r in rows]


WELCOME_MSG = "💪 <b>FitCoach Bot</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWelcome back, <b>{name}</b>.\n\nManage your clients, schedule training sessions, assign workout plans, and receive timely reminders — all in one place.\n\nSelect an option below to get started."
MAIN_MENU_MSG = "🏋️ <b>FitCoach Bot — Main Menu</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWhat would you like to manage today?"
CLIENTS_MENU_MSG = "👤 <b>Client Management</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nActive clients: <b>{count} / {max}</b>\n\nAdd, edit, remove clients, or view your full roster."
NO_CLIENTS_MSG = "👤 <b>No clients yet.</b>\n\nAdd your first client to get started."
MAX_CLIENTS_MSG = "⚠️ <b>Client limit reached ({max} clients).</b>\n\nRemove an existing client before adding a new one."
CLIENT_ADDED_MSG = "✅ <b>{name}</b> added to your roster.\n<i>Client ID: {id}</i>"
CLIENT_UPDATED_MSG = "✅ <b>{name}</b> profile updated successfully."
CONFIRM_DELETE_CLIENT_MSG = "⚠️ <b>Remove Client</b>\n\nRemove <b>{name}</b> from your roster?\n\n<i>All sessions and workout plans for this client will also be deleted. This cannot be undone.</i>"
CLIENT_DELETED_MSG = "✅ <b>{name}</b> has been removed from your roster."
SCHEDULE_MENU_MSG = "📅 <b>Schedule</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nView your schedule or manage sessions."
NO_CLIENTS_FOR_SESSION = "⚠️ No clients on your roster yet.\n\nAdd at least one client before scheduling a session."
SESSION_ADDED_MSG = "✅ <b>Session Scheduled</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👤 Client   : <b>{name}</b>\n📅 Date     : {date}\n🕐 Time     : {time}\n⏱ Duration : {duration} min\n\n<i>You'll receive a reminder 1 h and 2 h before this session.</i>"
SESSION_UPDATED_MSG = "✅ Session for <b>{name}</b> updated successfully."
CONFIRM_DELETE_SESSION_MSG = "⚠️ <b>Cancel Session</b>\n\nCancel the session with <b>{name}</b>\non {date} at {time}?\n\n<i>This action cannot be undone.</i>"
REMINDER_MSG = "🔔 <b>Session Reminder</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ <b>{hours} hour{plural}</b> until your session with:\n\n👤 <b>{name}</b>\n🕐 {time}  •  {duration} min"
WORKOUT_MENU_MSG = "📋 <b>Workout Plans</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nCreate and manage personalised workout plans for each client."
PLAN_ADDED_MSG = "✅ <b>Workout Plan Saved</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👤 Client : <b>{name}</b>\n📋 Plan   : {title}"


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤  Clients", callback_data="clients_menu"), InlineKeyboardButton("📅  Schedule", callback_data="schedule_menu")],
        [InlineKeyboardButton("📋  Workout Plans", callback_data="workout_menu")],
    ])

def clients_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕  Add Client", callback_data="add_client"), InlineKeyboardButton("✏️  Edit Client", callback_data="edit_client_start")],
        [InlineKeyboardButton("🗑  Remove Client", callback_data="delete_client"), InlineKeyboardButton("📋  View All", callback_data="list_clients")],
        [InlineKeyboardButton("🕑  History", callback_data="client_history")],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])

def schedule_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅  Today", callback_data="view_today"), InlineKeyboardButton("📆  This Week", callback_data="view_weekly"), InlineKeyboardButton("🗓  This Month", callback_data="view_monthly")],
        [InlineKeyboardButton("📋  All Sessions", callback_data="view_all_sessions")],
        [InlineKeyboardButton("➕  Add Session", callback_data="add_session"), InlineKeyboardButton("✏️  Edit Session", callback_data="edit_session_start")],
        [InlineKeyboardButton("🗑  Cancel Session", callback_data="delete_session")],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])

def workout_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕  New Plan", callback_data="add_plan"), InlineKeyboardButton("📋  All Plans", callback_data="list_plans")],
        [InlineKeyboardButton("👤  Plans by Client", callback_data="view_client_plan")],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])

def confirm_keyboard(confirm_data, cancel_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅  Confirm", callback_data=confirm_data), InlineKeyboardButton("✖  Cancel", callback_data=cancel_data)]])

def client_list_keyboard(clients, prefix):
    rows = [[InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")] for c in clients]
    rows.append([InlineKeyboardButton("✖  Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


async def reminder_loop(app, db):
    while True:
        try:
            chat_id = db.get_trainer_chat()
            if chat_id:
                for hours in REMINDER_HOURS:
                    for s in db.get_sessions_needing_reminder(hours):
                        await app.bot.send_message(chat_id=chat_id, parse_mode="HTML",
                            text=REMINDER_MSG.format(hours=hours, plural="" if hours==1 else "s",
                                                     name=s["client_name"], time=s["session_time"], duration=s["duration"]))
                        db.mark_reminded(s["id"], hours)
        except Exception as exc:
            logger.error("Reminder error: %s", exc)
        await asyncio.sleep(60)

def setup_scheduler(app, db):
    async def _start(application):
        asyncio.create_task(reminder_loop(application, db))
    app.post_init = _start


(ADD_CLIENT_NAME, ADD_CLIENT_PHONE, ADD_CLIENT_NOTES,
 EDIT_CLIENT_SELECT, EDIT_CLIENT_FIELD, EDIT_CLIENT_VALUE,
 ADD_SESSION_CLIENT, ADD_SESSION_DATE, ADD_SESSION_TIME, ADD_SESSION_DURATION, ADD_SESSION_NOTES,
 EDIT_SESSION_SELECT, EDIT_SESSION_FIELD, EDIT_SESSION_VALUE,
 ADD_PLAN_CLIENT, ADD_PLAN_TITLE, ADD_PLAN_CONTENT,
 CONFIRM_DELETE_CLIENT, CONFIRM_DELETE_SESSION) = range(19)


def fmt_daily(day, sessions):
    h = f"<b>📅 {day.strftime('%A, %d %B %Y')}</b>\n" + "─"*28 + "\n\n"
    if not sessions: return h + "<i>No sessions scheduled.</i>"
    body = ""
    for s in sorted(sessions, key=lambda x: x["session_time"]):
        body += f"🕐 <b>{s['session_time']}</b>  {s['client_name']}  <i>({s['duration']} min)</i>\n"
        if s.get("notes"): body += f"   📝 {s['notes']}\n"
        body += "\n"
    return h + body

def fmt_weekly(monday, week):
    txt = f"<b>📆 Week of {monday.strftime('%d %B %Y')}</b>\n" + "─"*28 + "\n\n"
    for i, (d, sessions) in enumerate(week.items()):
        marker = "▶" if d == date.today() else "  "
        txt += f"{marker} <b>{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][i]} {d.strftime('%d/%m')}</b>\n"
        if sessions:
            for s in sorted(sessions, key=lambda x: x["session_time"]):
                txt += f"    {s['session_time']} — {s['client_name']} ({s['duration']}m)\n"
        else: txt += "    <i>Free</i>\n"
        txt += "\n"
    return txt

def fmt_monthly(today, sessions):
    txt = f"<b>🗓 {today.strftime('%B %Y')}</b>\n" + "─"*28 + "\n\n"
    by_day = {}
    for s in sessions: by_day.setdefault(s["session_date"], []).append(s)
    if not by_day: return txt + "<i>No sessions this month.</i>"
    for d in sorted(by_day):
        day_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
        txt += f"{'▶ ' if day_obj==today else ''}<b>{day_obj.strftime('%a %d')}</b>\n"
        for s in sorted(by_day[d], key=lambda x: x["session_time"]):
            txt += f"  {s['session_time']} {s['client_name']} ({s['duration']}m)\n"
        txt += "\n"
    total = sum(len(v) for v in by_day.values())
    txt += f"<i>Total: {total} session{'s' if total!=1 else ''} this month</i>"
    return txt


db = Database()

async def start(update, context):
    db.set_trainer_chat(update.effective_chat.id)
    await update.message.reply_text(WELCOME_MSG.format(name=update.effective_user.first_name), reply_markup=main_menu_keyboard(), parse_mode="HTML")

async def cmd_main_menu(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(MAIN_MENU_MSG, reply_markup=main_menu_keyboard(), parse_mode="HTML")

async def cmd_clients_menu(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(CLIENTS_MENU_MSG.format(count=len(db.get_all_clients()), max=MAX_CLIENTS), reply_markup=clients_menu_keyboard(), parse_mode="HTML")

async def cmd_list_clients(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return
    txt = "<b>👤 Client Roster</b>\n" + "─"*28 + "\n\n"
    for i, c in enumerate(clients, 1):
        ns = db.get_next_session_for_client(c["id"])
        txt += f"<b>{i:02d}. {c['name']}</b>\n   📞 {c['phone'] or '—'}\n   📝 {c['notes'] or '—'}\n   📅 Joined: {c['created_at']}\n"
        if ns: txt += f"   ⏭ Next: <i>{ns}</i>\n"
        txt += "\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>… truncated</i>"
    await q.edit_message_text(txt, reply_markup=clients_menu_keyboard(), parse_mode="HTML")

async def add_client_start(update, context):
    q = update.callback_query; await q.answer()
    if len(db.get_all_clients()) >= MAX_CLIENTS:
        await q.edit_message_text(MAX_CLIENTS_MSG.format(max=MAX_CLIENTS), reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    await q.edit_message_text("➕ <b>New Client</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nEnter the client's full name:", parse_mode="HTML")
    return ADD_CLIENT_NAME

async def add_client_name(update, context):
    context.user_data["nc"] = {"name": update.message.text.strip()}
    await update.message.reply_text("Enter the client's phone number:\n<i>(Type <code>skip</code> to leave blank)</i>", parse_mode="HTML")
    return ADD_CLIENT_PHONE

async def add_client_phone(update, context):
    txt = update.message.text.strip()
    context.user_data["nc"]["phone"] = "" if txt.lower()=="skip" else txt
    await update.message.reply_text("Any notes for this client?\n<i>e.g. injuries, goals, preferences\n(Type <code>skip</code> to leave blank)</i>", parse_mode="HTML")
    return ADD_CLIENT_NOTES

async def add_client_notes(update, context):
    d = context.user_data["nc"]
    d["notes"] = "" if update.message.text.strip().lower()=="skip" else update.message.text.strip()
    cid = db.add_client(d["name"], d["phone"], d["notes"])
    await update.message.reply_text(CLIENT_ADDED_MSG.format(name=d["name"], id=cid), reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def edit_client_start(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    await q.edit_message_text("<b>✏️ Edit Client</b>\n\nSelect a client to edit:", reply_markup=client_list_keyboard(clients, "editcl"), parse_mode="HTML")
    return EDIT_CLIENT_SELECT

async def edit_client_select(update, context):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["edit_cid"] = cid
    txt = f"<b>✏️ Editing: {c['name']}</b>\n\n📞 Phone : {c['phone'] or '—'}\n📝 Notes : {c['notes'] or '—'}\n\nWhat would you like to edit?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Name", callback_data="editcl_field:name"), InlineKeyboardButton("📞 Phone", callback_data="editcl_field:phone")],
        [InlineKeyboardButton("📝 Notes", callback_data="editcl_field:notes")],
        [InlineKeyboardButton("✖ Cancel", callback_data="clients_menu")],
    ])
    await q.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    return EDIT_CLIENT_FIELD

async def edit_client_field(update, context):
    q = update.callback_query; await q.answer()
    field = q.data.split(":")[1]; context.user_data["edit_cl_field"] = field
    labels = {"name": "full name", "phone": "phone number", "notes": "notes"}
    await q.edit_message_text(f"Enter the new <b>{labels[field]}</b>:\n<i>(Type <code>skip</code> to clear)</i>", parse_mode="HTML")
    return EDIT_CLIENT_VALUE

async def edit_client_value(update, context):
    cid = context.user_data["edit_cid"]; field = context.user_data["edit_cl_field"]
    value = "" if update.message.text.strip().lower()=="skip" else update.message.text.strip()
    c = db.get_client(cid); updated = {k: c[k] for k in ("name","phone","notes")}; updated[field] = value
    db.update_client(cid, updated["name"], updated["phone"], updated["notes"])
    await update.message.reply_text(CLIENT_UPDATED_MSG.format(name=updated["name"]), reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def delete_client_start(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    await q.edit_message_text("<b>🗑 Remove Client</b>\n\nSelect the client to remove:", reply_markup=client_list_keyboard(clients, "del_client"), parse_mode="HTML")
    return CONFIRM_DELETE_CLIENT

async def confirm_delete_client(update, context):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    if not c:
        await q.edit_message_text("Client not found.", reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    context.user_data["del_cid"] = cid
    await q.edit_message_text(CONFIRM_DELETE_CLIENT_MSG.format(name=c["name"]), reply_markup=confirm_keyboard("confirm_del_client","cancel_del_client"), parse_mode="HTML")
    return CONFIRM_DELETE_CLIENT

async def execute_delete_client(update, context):
    q = update.callback_query; await q.answer()
    if q.data == "confirm_del_client":
        cid = context.user_data.get("del_cid"); c = db.get_client(cid); db.delete_client(cid)
        await q.edit_message_text(CLIENT_DELETED_MSG.format(name=c["name"]), reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    else:
        await q.edit_message_text("Deletion cancelled.", reply_markup=clients_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def cmd_client_history(update, context):
    q = update.callback_query; await q.answer()
    history = db.get_history()
    if not history:
        await q.edit_message_text("<b>🕑 Client History</b>\n\n<i>No history yet.</i>", reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return
    txt = "<b>🕑 Client History</b>\n" + "─"*28 + "\n\n"; kb_rows = []
    for h in history:
        icon = "✅" if h["action"]=="ADDED" else "🗑"
        txt += f"{icon} <b>{h['client_name']}</b>  <i>{h['action_at'][:16]}</i>\n"
        if h.get("phone"): txt += f"   📞 {h['phone']}\n"
        if h.get("notes"): txt += f"   📝 {h['notes']}\n"
        txt += "\n"
        kb_rows.append([InlineKeyboardButton(f"🗑 Delete: {h['client_name']} ({h['action_at'][:10]})", callback_data=f"del_hist:{h['id']}")])
    kb_rows.append([InlineKeyboardButton("↩ Back", callback_data="clients_menu")])
    if len(txt) > 3800: txt = txt[:3790] + "\n<i>… truncated</i>"
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")

async def delete_history_entry(update, context):
    q = update.callback_query; await q.answer()
    db.delete_history_entry(int(q.data.split(":")[1]))
    history = db.get_history()
    if not history:
        await q.edit_message_text("<b>🕑 Client History</b>\n\n<i>No history yet.</i>", reply_markup=clients_menu_keyboard(), parse_mode="HTML"); return
    txt = "<b>🕑 Client History</b>\n" + "─"*28 + "\n\n"; kb_rows = []
    for h in history:
        icon = "✅" if h["action"]=="ADDED" else "🗑"
        txt += f"{icon} <b>{h['client_name']}</b>  <i>{h['action_at'][:16]}</i>\n"
        if h.get("phone"): txt += f"   📞 {h['phone']}\n"
        if h.get("notes"): txt += f"   📝 {h['notes']}\n"
        txt += "\n"
        kb_rows.append([InlineKeyboardButton(f"🗑 Delete: {h['client_name']} ({h['action_at'][:10]})", callback_data=f"del_hist:{h['id']}")])
    kb_rows.append([InlineKeyboardButton("↩ Back", callback_data="clients_menu")])
    if len(txt) > 3800: txt = txt[:3790] + "\n<i>… truncated</i>"
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")

async def cmd_schedule_menu(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(SCHEDULE_MENU_MSG, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_today(update, context):
    q = update.callback_query; await q.answer()
    today = date.today()
    await q.edit_message_text(fmt_daily(today, db.get_sessions_for_date(today)), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_weekly(update, context):
    q = update.callback_query; await q.answer()
    today = date.today(); monday = today - timedelta(days=today.weekday())
    week = {monday + timedelta(days=i): db.get_sessions_for_date(monday + timedelta(days=i)) for i in range(7)}
    await q.edit_message_text(fmt_weekly(monday, week), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_monthly(update, context):
    q = update.callback_query; await q.answer()
    today = date.today(); first_day = today.replace(day=1)
    last_day = (today.replace(year=today.year+1, month=1, day=1) if today.month==12 else today.replace(month=today.month+1, day=1)) - timedelta(days=1)
    await q.edit_message_text(fmt_monthly(today, db.get_sessions_for_range(first_day, last_day)), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def cmd_view_all_sessions(update, context):
    q = update.callback_query; await q.answer()
    sessions = db.get_all_sessions(limit=50)
    if not sessions:
        await q.edit_message_text("<b>📋 All Sessions</b>\n\n<i>No sessions found.</i>", reply_markup=schedule_menu_keyboard(), parse_mode="HTML"); return
    txt = "<b>📋 All Sessions</b>\n" + "─"*28 + "\n\n"
    for s in sessions:
        txt += f"📅 <b>{s['session_date']}</b>  🕐 {s['session_time']}\n   👤 {s['client_name']}  ⏱ {s['duration']} min\n"
        if s.get("notes"): txt += f"   📝 {s['notes']}\n"
        txt += "\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>… showing latest 50 sessions</i>"
    await q.edit_message_text(txt, reply_markup=schedule_menu_keyboard(), parse_mode="HTML")

async def add_session_start(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_FOR_SESSION, reply_markup=schedule_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    await q.edit_message_text("<b>📅 New Session</b>\n\nSelect a client:", reply_markup=client_list_keyboard(clients, "sess_client"), parse_mode="HTML")
    return ADD_SESSION_CLIENT

async def add_session_client(update, context):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1]); client = db.get_client(cid)
    context.user_data["ns"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(f"<b>📅 New Session — {client['name']}</b>\n\nEnter the date:\n<code>Format: DD/MM/YYYY  (e.g. 25/06/2025)</code>", parse_mode="HTML")
    return ADD_SESSION_DATE

async def add_session_date(update, context):
    try:
        d = datetime.strptime(update.message.text.strip(), "%d/%m/%Y").date()
        if d < date.today():
            await update.message.reply_text("⚠️ Date is in the past. Enter a future date (DD/MM/YYYY):"); return ADD_SESSION_DATE
        context.user_data["ns"]["date"] = d
        await update.message.reply_text(f"<b>📅 Session — {context.user_data['ns']['client_name']}</b>\n\nEnter the start time:\n<code>Format: HH:MM  (e.g. 09:30)</code>", parse_mode="HTML")
        return ADD_SESSION_TIME
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use DD/MM/YYYY:"); return ADD_SESSION_DATE

async def add_session_time(update, context):
    try:
        t = datetime.strptime(update.message.text.strip(), "%H:%M").time()
        context.user_data["ns"]["time"] = t
        await update.message.reply_text("Session duration in minutes:\n<code>e.g. 60</code>", parse_mode="HTML")
        return ADD_SESSION_DURATION
    except ValueError:
        await update.message.reply_text("⚠️ Invalid format. Use HH:MM (e.g. 09:30):"); return ADD_SESSION_TIME

async def add_session_duration(update, context):
    try:
        dur = int(update.message.text.strip())
        if not (1 <= dur <= 300): raise ValueError
        context.user_data["ns"]["duration"] = dur
        await update.message.reply_text("Session notes (type <code>skip</code> to leave blank):", parse_mode="HTML")
        return ADD_SESSION_NOTES
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid number of minutes (e.g. 60):"); return ADD_SESSION_DURATION

async def add_session_notes(update, context):
    txt = update.message.text.strip(); d = context.user_data["ns"]
    d["notes"] = "" if txt.lower()=="skip" else txt
    db.add_session(d["client_id"], d["date"], d["time"], d["duration"], d["notes"])
    await update.message.reply_text(SESSION_ADDED_MSG.format(name=d["client_name"], date=d["date"].strftime("%A, %d %B %Y"), time=d["time"].strftime("%H:%M"), duration=d["duration"]), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def edit_session_start(update, context):
    q = update.callback_query; await q.answer()
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await q.edit_message_text("No upcoming sessions to edit.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{s['session_date']}  {s['session_time']} — {s['client_name']}", callback_data=f"editsess:{s['id']}")] for s in sessions]
    kb.append([InlineKeyboardButton("✖ Cancel", callback_data="schedule_menu")])
    await q.edit_message_text("<b>✏️ Edit Session</b>\n\nSelect a session to edit:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return EDIT_SESSION_SELECT

async def edit_session_select(update, context):
    q = update.callback_query; await q.answer()
    sid = int(q.data.split(":")[1]); s = db.get_session(sid)
    context.user_data["edit_sid"] = sid
    txt = f"<b>✏️ Editing Session</b>\n\n👤 {s['client_name']}\n📅 {s['session_date']}  🕐 {s['session_time']}\n⏱ {s['duration']} min\n📝 {s['notes'] or '—'}\n\nWhat would you like to change?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Date", callback_data="editsess_field:date"), InlineKeyboardButton("🕐 Time", callback_data="editsess_field:time")],
        [InlineKeyboardButton("⏱ Duration", callback_data="editsess_field:duration"), InlineKeyboardButton("📝 Notes", callback_data="editsess_field:notes")],
        [InlineKeyboardButton("✖ Cancel", callback_data="schedule_menu")],
    ])
    await q.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    return EDIT_SESSION_FIELD

async def edit_session_field(update, context):
    q = update.callback_query; await q.answer()
    field = q.data.split(":")[1]; context.user_data["edit_sess_field"] = field
    prompts = {"date": "Enter new date:\n<code>Format: DD/MM/YYYY</code>", "time": "Enter new time:\n<code>Format: HH:MM</code>",
               "duration": "Enter new duration in minutes:\n<code>e.g. 60</code>", "notes": "Enter new notes:\n<i>(Type <code>skip</code> to clear)</i>"}
    await q.edit_message_text(prompts[field], parse_mode="HTML")
    return EDIT_SESSION_VALUE

async def edit_session_value(update, context):
    sid = context.user_data["edit_sid"]; field = context.user_data["edit_sess_field"]; txt = update.message.text.strip()
    s = db.get_session(sid)
    try:
        new_date = datetime.strptime(s["session_date"], "%Y-%m-%d").date()
        new_time = datetime.strptime(s["session_time"], "%H:%M").time()
        new_duration = s["duration"]; new_notes = s["notes"] or ""
        if field == "date":
            new_date = datetime.strptime(txt, "%d/%m/%Y").date()
            if new_date < date.today():
                await update.message.reply_text("⚠️ Date is in the past. Try again (DD/MM/YYYY):"); return EDIT_SESSION_VALUE
        elif field == "time": new_time = datetime.strptime(txt, "%H:%M").time()
        elif field == "duration":
            new_duration = int(txt)
            if not (1 <= new_duration <= 300): raise ValueError
        elif field == "notes": new_notes = "" if txt.lower()=="skip" else txt
        db.update_session(sid, new_date, new_time, new_duration, new_notes)
        await update.message.reply_text(SESSION_UPDATED_MSG.format(name=s["client_name"]), reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        hints = {"date":"DD/MM/YYYY","time":"HH:MM","duration":"a number 1-300","notes":"any text"}
        await update.message.reply_text(f"⚠️ Invalid input. Expected: <code>{hints[field]}</code>", parse_mode="HTML")
        return EDIT_SESSION_VALUE

async def delete_session_start(update, context):
    q = update.callback_query; await q.answer()
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await q.edit_message_text("No upcoming sessions found.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{s['session_date']}  {s['session_time']} — {s['client_name']}", callback_data=f"del_sess:{s['id']}")] for s in sessions]
    kb.append([InlineKeyboardButton("↩ Back", callback_data="schedule_menu")])
    await q.edit_message_text("<b>🗑 Cancel Session</b>\n\nSelect the session to remove:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return CONFIRM_DELETE_SESSION

async def confirm_delete_session(update, context):
    q = update.callback_query; await q.answer()
    sid = int(q.data.split(":")[1]); s = db.get_session(sid)
    context.user_data["del_sid"] = sid
    await q.edit_message_text(CONFIRM_DELETE_SESSION_MSG.format(name=s["client_name"], date=s["session_date"], time=s["session_time"]), reply_markup=confirm_keyboard("confirm_del_sess","cancel_del_sess"), parse_mode="HTML")
    return CONFIRM_DELETE_SESSION

async def execute_delete_session(update, context):
    q = update.callback_query; await q.answer()
    if q.data == "confirm_del_sess":
        db.delete_session(context.user_data.get("del_sid"))
        await q.edit_message_text("✅ Session removed from your schedule.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
    else:
        await q.edit_message_text("Deletion cancelled.", reply_markup=schedule_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def cmd_workout_menu(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(WORKOUT_MENU_MSG, reply_markup=workout_menu_keyboard(), parse_mode="HTML")

async def cmd_list_plans(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients(); txt, any_plan = "<b>📋 Workout Plans</b>\n" + "─"*28 + "\n\n", False
    for c in clients:
        plans = db.get_plans_for_client(c["id"])
        if plans:
            any_plan = True; txt += f"<b>👤 {c['name']}</b>\n"
            for p in plans: txt += f"  • {p['title']}  <i>({p['created_at']})</i>\n"
            txt += "\n"
    if not any_plan: txt += "<i>No workout plans yet.</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(), parse_mode="HTML")

async def add_plan_start(update, context):
    q = update.callback_query; await q.answer()
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(NO_CLIENTS_MSG, reply_markup=workout_menu_keyboard(), parse_mode="HTML"); return ConversationHandler.END
    await q.edit_message_text("<b>📋 New Workout Plan</b>\n\nSelect a client:", reply_markup=client_list_keyboard(clients, "plan_client"), parse_mode="HTML")
    return ADD_PLAN_CLIENT

async def add_plan_client(update, context):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1]); client = db.get_client(cid)
    context.user_data["np"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(f"<b>📋 Plan for {client['name']}</b>\n\nEnter the plan title:\n<i>e.g. Week 1 — Strength Foundation</i>", parse_mode="HTML")
    return ADD_PLAN_TITLE

async def add_plan_title(update, context):
    context.user_data["np"]["title"] = update.message.text.strip()
    await update.message.reply_text("<b>📋 Workout Plan Content</b>\n\nEnter the full workout plan:\n\n<code>Day 1 — Push\nBench Press 4×8\nShoulder Press 3×10\n\nDay 2 — Pull\nDeadlift 4×5\nRows 3×12</code>", parse_mode="HTML")
    return ADD_PLAN_CONTENT

async def add_plan_content(update, context):
    d = context.user_data["np"]; d["content"] = update.message.text.strip()
    db.add_plan(d["client_id"], d["title"], d["content"])
    await update.message.reply_text(PLAN_ADDED_MSG.format(name=d["client_name"], title=d["title"]), reply_markup=workout_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def cmd_view_client_plan(update, context):
    q = update.callback_query; await q.answer()
    clients = [c for c in db.get_all_clients() if db.get_plans_for_client(c["id"])]
    if not clients:
        await q.edit_message_text("No workout plans found.", reply_markup=workout_menu_keyboard(), parse_mode="HTML"); return
    await q.edit_message_text("<b>📋 View Plan</b>\n\nSelect a client:", reply_markup=client_list_keyboard(clients, "view_plan"), parse_mode="HTML")

async def cmd_show_client_plans(update, context):
    q = update.callback_query; await q.answer()
    cid = int(q.data.split(":")[1]); client = db.get_client(cid); plans = db.get_plans_for_client(cid)
    if not plans:
        await q.edit_message_text(f"No plans for {client['name']}.", reply_markup=workout_menu_keyboard(), parse_mode="HTML"); return
    txt = f"<b>📋 {client['name']} — Workout Plans</b>\n" + "─"*28 + "\n\n"
    for p in plans: txt += f"<b>{p['title']}</b>  <i>{p['created_at']}</i>\n{p['content']}\n\n" + "─"*20 + "\n\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>… truncated</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(), parse_mode="HTML")

async def cancel(update, context):
    await update.message.reply_text("Operation cancelled.", reply_markup=main_menu_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def unknown_callback(update, context):
    await update.callback_query.answer("Unknown action.", show_alert=False)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    add_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_client_start, pattern="^add_client$")],
        states={ADD_CLIENT_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_name)],ADD_CLIENT_PHONE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_phone)],ADD_CLIENT_NOTES:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_notes)]},
        fallbacks=[CommandHandler("cancel",cancel)])
    edit_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_client_start, pattern="^edit_client_start$")],
        states={EDIT_CLIENT_SELECT:[CallbackQueryHandler(edit_client_select,pattern="^editcl:")],EDIT_CLIENT_FIELD:[CallbackQueryHandler(edit_client_field,pattern="^editcl_field:")],EDIT_CLIENT_VALUE:[MessageHandler(filters.TEXT&~filters.COMMAND,edit_client_value)]},
        fallbacks=[CommandHandler("cancel",cancel)])
    del_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_client_start, pattern="^delete_client$")],
        states={CONFIRM_DELETE_CLIENT:[CallbackQueryHandler(confirm_delete_client,pattern="^del_client:"),CallbackQueryHandler(execute_delete_client,pattern="^(confirm|cancel)_del_client$")]},
        fallbacks=[CommandHandler("cancel",cancel)])
    add_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_session_start, pattern="^add_session$")],
        states={ADD_SESSION_CLIENT:[CallbackQueryHandler(add_session_client,pattern="^sess_client:")],ADD_SESSION_DATE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_date)],ADD_SESSION_TIME:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_time)],ADD_SESSION_DURATION:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_duration)],ADD_SESSION_NOTES:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_notes)]},
        fallbacks=[CommandHandler("cancel",cancel)])
    edit_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_session_start, pattern="^edit_session_start$")],
        states={EDIT_SESSION_SELECT:[CallbackQueryHandler(edit_session_select,pattern="^editsess:")],EDIT_SESSION_FIELD:[CallbackQueryHandler(edit_session_field,pattern="^editsess_field:")],EDIT_SESSION_VALUE:[MessageHandler(filters.TEXT&~filters.COMMAND,edit_session_value)]},
        fallbacks=[CommandHandler("cancel",cancel)])
    del_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_session_start, pattern="^delete_session$")],
        states={CONFIRM_DELETE_SESSION:[CallbackQueryHandler(confirm_delete_session,pattern="^del_sess:"),CallbackQueryHandler(execute_delete_session,pattern="^(confirm|cancel)_del_sess$")]},
        fallbacks=[CommandHandler("cancel",cancel)])
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_plan_start, pattern="^add_plan$")],
        states={ADD_PLAN_CLIENT:[CallbackQueryHandler(add_plan_client,pattern="^plan_client:")],ADD_PLAN_TITLE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_plan_title)],ADD_PLAN_CONTENT:[MessageHandler(filters.TEXT&~filters.COMMAND,add_plan_content)]},
        fallbacks=[CommandHandler("cancel",cancel)])

    app.add_handler(CommandHandler("start", start))
    for conv in [add_client_conv, edit_client_conv, del_client_conv, add_session_conv, edit_session_conv, del_session_conv, add_plan_conv]:
        app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(cmd_main_menu,         pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_clients_menu,      pattern="^clients_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_clients,      pattern="^list_clients$"))
    app.add_handler(CallbackQueryHandler(cmd_client_history,    pattern="^client_history$"))
    app.add_handler(CallbackQueryHandler(delete_history_entry,  pattern="^del_hist:"))
    app.add_handler(CallbackQueryHandler(cmd_schedule_menu,     pattern="^schedule_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_view_today,        pattern="^view_today$"))
    app.add_handler(CallbackQueryHandler(cmd_view_weekly,       pattern="^view_weekly$"))
    app.add_handler(CallbackQueryHandler(cmd_view_monthly,      pattern="^view_monthly$"))
    app.add_handler(CallbackQueryHandler(cmd_view_all_sessions, pattern="^view_all_sessions$"))
    app.add_handler(CallbackQueryHandler(cmd_workout_menu,      pattern="^workout_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_plans,        pattern="^list_plans$"))
    app.add_handler(CallbackQueryHandler(cmd_view_client_plan,  pattern="^view_client_plan$"))
    app.add_handler(CallbackQueryHandler(cmd_show_client_plans, pattern="^view_plan:"))
    app.add_handler(CallbackQueryHandler(unknown_callback))

    setup_scheduler(app, db)
    logger.info("🏋️  FitCoach Bot v2 is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
