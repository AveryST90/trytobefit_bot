"""
╔══════════════════════════════════════════════════════════════════╗
║                     FITCOACH BOT  v4                            ║
║  NEW: Body measurements per client — weight, chest, waist,     ║
║       hips, legs, arms — multiple entries, sorted by date,     ║
║       edit & delete individual entries, full history view       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, logging, sqlite3, asyncio, calendar
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)

BOT_TOKEN      = os.getenv("BOT_TOKEN", "8728837807:AAFpE51RGvnG0LzWfZyt_KQO6dctj9Tssf4")
REMINDER_HOURS = [1, 2]
MAX_CLIENTS    = 50
DB_PATH        = Path(os.getenv("DB_PATH", "fitcoach.db"))

logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
#  TRANSLATIONS
# ═══════════════════════════════════════════════════════════════════
DAYS_RO  = ["Luni","Marți","Miercuri","Joi","Vineri","Sâmbătă","Duminică"]
DAYS_EN  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
DAYS_SHORT_RO = ["Lun","Mar","Mie","Joi","Vin","Sâm","Dum"]
DAYS_SHORT_EN = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
MONTHS_RO = ["","Ianuarie","Februarie","Martie","Aprilie","Mai","Iunie","Iulie","August","Septembrie","Octombrie","Noiembrie","Decembrie"]
MONTHS_EN = ["","January","February","March","April","May","June","July","August","September","October","November","December"]

T = {
    "EN": {
        "welcome": "💪 <b>FitCoach Bot</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWelcome back, <b>{name}</b>.\n\nManage your clients, schedule training sessions, assign workout plans, and receive timely reminders — all in one place.\n\nSelect an option below to get started.",
        "main_menu": "🏋️ <b>FitCoach Bot — Main Menu</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWhat would you like to manage today?",
        "clients_menu": "👤 <b>Client Management</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nActive clients: <b>{count} / {max}</b>\n\nAdd, edit, remove clients, or view your full roster.",
        "no_clients": "👤 <b>No clients yet.</b>\n\nAdd your first client to get started.",
        "max_clients": "⚠️ <b>Client limit reached ({max} clients).</b>\n\nRemove an existing client before adding a new one.",
        "client_added": "✅ <b>{name}</b> added to your roster.",
        "client_updated": "✅ <b>{name}</b> profile updated successfully.",
        "confirm_del_client": "⚠️ <b>Remove Client</b>\n\nRemove <b>{name}</b> from your roster?\n\n<i>All sessions and workout plans will also be deleted. This cannot be undone.</i>",
        "client_deleted": "✅ <b>{name}</b> has been removed from your roster.",
        "schedule_menu": "📅 <b>Schedule</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nView your schedule or manage sessions.",
        "no_clients_for_session": "⚠️ No clients on your roster yet.\n\nAdd at least one client before scheduling a session.",
        "session_added": "✅ <b>Session Scheduled</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👤 Client   : <b>{name}</b>\n📅 Date     : {date}\n⏱ Duration : {duration} min\n\n<i>You'll receive a reminder 1h and 2h before this session.</i>",
        "session_updated": "✅ Session for <b>{name}</b> updated successfully.",
        "confirm_del_session": "⚠️ <b>Cancel Session</b>\n\nCancel the session with <b>{name}</b>\non {date}?\n\n<i>This action cannot be undone.</i>",
        "session_deleted": "✅ Session removed from your schedule.",
        "reminder": "🔔 <b>Session Reminder</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ <b>{hours} hour{plural}</b> until your session with:\n\n👤 <b>{name}</b>\n🕐 {time}  •  {duration} min",
        "workout_menu": "📋 <b>Workout Plans</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nCreate and manage personalised workout plans for each client.",
        "plan_added": "✅ <b>Workout Plan Saved</b>\n\n👤 Client : <b>{name}</b>\n📋 Plan   : {title}",
        "no_plans": "No workout plans found.",
        "cancelled": "Operation cancelled.",
        "deletion_cancelled": "Deletion cancelled.",
        "client_not_found": "Client not found.",
        "no_upcoming": "No upcoming sessions found.",
        "no_sessions_edit": "No upcoming sessions to edit.",
        "no_sessions_all": "No sessions found.",
        "history_empty": "No history yet.",
        "pkg_month_prompt": "Enter the month for this package:\n<code>Format: MM/YYYY  (e.g. 06/2025)</code>",
        "pkg_bought_prompt": "How many sessions did <b>{name}</b> buy for {month}?",
        "pkg_used_prompt": "How many sessions has <b>{name}</b> used so far in {month}?\n<i>(Type 0 if none yet)</i>",
        "pkg_saved": "✅ Package saved: <b>{name}</b> — {month}\n📦 Bought: {bought}  |  ✅ Used: {used}  |  🔄 Left: {left}",
        "pkg_menu": "📦 <b>Session Packages</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage monthly session packages per client.",
        "pkg_none": "No packages found for this client.",
        "sessions_left": "sessions left",
        "of": "of",
        "free": "Free",
        "no_sessions_day": "No sessions scheduled.",
        "total": "Total",
        "session_s": "session",
        "sessions_s": "sessions",
        "this_month": "this month",
        "joined": "Joined",
        "next": "Next",
        "btn_clients": "👤  Clients",
        "btn_schedule": "📅  Schedule",
        "btn_plans": "📋  Workout Plans",
        "btn_add_client": "➕  Add Client",
        "btn_edit_client": "✏️  Edit Client",
        "btn_del_client": "🗑  Remove Client",
        "btn_view_all": "📋  View All",
        "btn_history": "🕑  History",
        "btn_main_menu": "↩  Main Menu",
        "btn_today": "📅  Today",
        "btn_week": "📆  This Week",
        "btn_month": "🗓  This Month",
        "btn_all_sess": "📋  All Sessions",
        "btn_add_sess": "➕  Add Session",
        "btn_edit_sess": "✏️  Edit Session",
        "btn_del_sess": "🗑  Cancel Session",
        "btn_new_plan": "➕  New Plan",
        "btn_all_plans": "📋  All Plans",
        "btn_plans_by": "👤  Plans by Client",
        "btn_pkg": "📦  Packages",
        "btn_add_pkg": "➕  Add Package",
        "btn_view_pkg": "📊  View Packages",
        "btn_edit_used": "✏️  Update Used",
        "btn_confirm": "✅  Confirm",
        "btn_cancel": "✖  Cancel",
        "btn_back": "↩  Back",
        "select_client": "Select a client:",
        "select_edit_field": "What would you like to edit?",
        "enter_name": "➕ <b>New Client</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nEnter the client's full name:",
        "enter_phone": "Enter the client's phone number:\n<i>(Type <code>skip</code> to leave blank)</i>",
        "enter_notes": "Any notes for this client?\n<i>e.g. injuries, goals, preferences\n(Type <code>skip</code> to leave blank)</i>",
        "field_name": "full name", "field_phone": "phone number", "field_notes": "notes",
        "field_sessions_bought": "sessions bought this month",
        "field_sessions_used": "sessions used this month",
        "enter_field": "Enter the new <b>{label}</b>:\n<i>(Type <code>skip</code> to clear)</i>",
        "enter_field_num": "Enter the new <b>{label}</b>:\n<i>(Enter a number, e.g. 8)</i>",
        "invalid_date": "⚠️ Invalid format. Use DD/MM/YYYY:",
        "invalid_time": "⚠️ Invalid format. Use HH:MM (e.g. 09:30):",
        "invalid_duration": "⚠️ Enter a valid number of minutes (e.g. 60):",
        "invalid_number": "⚠️ Enter a valid number:",
        "past_date": "⚠️ Date is in the past. Enter a future date (DD/MM/YYYY):",
        "date_prompt": "Enter the date:\n<code>Format: DD/MM/YYYY  (e.g. 25/06/2025)</code>",
        "time_prompt": "Enter the start time:\n<code>Format: HH:MM  (e.g. 09:30)</code>",
        "duration_prompt": "Session duration in minutes:\n<code>e.g. 60</code>",
        "notes_prompt": "Session notes:\n<i>(Type <code>skip</code> to leave blank)</i>",
        "roster_title": "<b>👤 Client Roster</b>\n",
        "history_title": "<b>🕑 Client History</b>\n",
        "all_sessions_title": "<b>📋 All Sessions</b>\n",
        "editing_session": "<b>✏️ Editing Session</b>\n\n👤 {name}\n📅 {date}\n⏱ {duration} min\n📝 {notes}\n\nWhat would you like to change?",
        "editing_client": "<b>✏️ Editing: {name}</b>\n\n📞 Phone : {phone}\n📝 Notes : {notes}\n📦 Sessions bought : {bought}\n✅ Sessions used  : {used}\n\nWhat would you like to edit?",
        "del_hist_btn": "🗑 Delete: {name} ({date})",
        "week_of": "Week of",
        "select_sess_edit": "<b>✏️ Edit Session</b>\n\nSelect a session to edit:",
        "select_sess_del": "<b>🗑 Cancel Session</b>\n\nSelect the session to remove:",
        "plan_title_prompt": "Enter the plan title:\n<i>e.g. Week 1 — Strength Foundation</i>",
        "plan_content_prompt": "<b>📋 Workout Plan Content</b>\n\nEnter the full workout plan:\n\n<code>Day 1 — Push\nBench Press 4×8\nShoulder Press 3×10\n\nDay 2 — Pull\nDeadlift 4×5\nRows 3×12</code>",
        "view_plan_title": "<b>📋 View Plan</b>\n\nSelect a client:",
        "invalid_month": "⚠️ Invalid format. Use MM/YYYY (e.g. 06/2025):",
        "pkg_update_used_prompt": "Enter the new number of <b>sessions used</b> for {name} in {month}:",
        "pkg_not_found": "No package found for this month.",
        "language_prompt": "🌍 <b>Choose your language / Alege limba</b>",
        # ── Body measurements ──
        "body_menu": "📏 <b>Body Measurements</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nTrack body measurements for each client.",
        "btn_body": "📏  Body Measurements",
        "btn_add_body": "➕  Add Measurement",
        "btn_view_body": "📊  View History",
        "btn_edit_body": "✏️  Edit Entry",
        "btn_del_body": "🗑  Delete Entry",
        "body_select_client": "Select a client to manage measurements:",
        "body_date_prompt": "Enter the measurement date:\n<code>Format: DD/MM/YYYY</code>",
        "body_weight_prompt": "⚖️ Weight (kg):\n<i>(e.g. 75.5 — type <code>skip</code> to leave blank)</i>",
        "body_chest_prompt": "📏 Chest circumference (cm):\n<i>(type <code>skip</code> to leave blank)</i>",
        "body_waist_prompt": "📏 Waist circumference (cm):\n<i>(type <code>skip</code> to leave blank)</i>",
        "body_hips_prompt": "📏 Hips circumference (cm):\n<i>(type <code>skip</code> to leave blank)</i>",
        "body_leg_prompt": "📏 Leg circumference (cm):\n<i>(type <code>skip</code> to leave blank)</i>",
        "body_arm_prompt": "📏 Arm circumference (cm):\n<i>(type <code>skip</code> to leave blank)</i>",
        "body_saved": "✅ Measurements saved for <b>{name}</b> on {date}",
        "body_none": "No measurements recorded yet for this client.",
        "body_updated": "✅ Measurement entry updated.",
        "body_deleted": "✅ Measurement entry deleted.",
        "body_select_entry": "Select an entry to {action}:",
        "body_confirm_delete": "⚠️ Delete the measurement entry from <b>{date}</b> for <b>{name}</b>?\n\nThis cannot be undone.",
        "invalid_decimal": "⚠️ Enter a valid number (e.g. 75.5) or <code>skip</code>:",
        "body_edit_field_prompt": "What would you like to edit?",
        "lbl_weight": "⚖️ Weight",
        "lbl_chest": "📏 Chest",
        "lbl_waist": "📏 Waist",
        "lbl_hips": "📏 Hips",
        "lbl_leg": "📏 Leg",
        "lbl_arm": "📏 Arm",
        "unit_kg": "kg",
        "unit_cm": "cm",
    },
    "RO": {
        "welcome": "💪 <b>FitCoach Bot</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nBine ai revenit, <b>{name}</b>.\n\nGestionează clienții, programează antrenamentele, atribuie planuri de exerciții și primește memento-uri — totul într-un singur loc.\n\nSelectează o opțiune pentru a începe.",
        "main_menu": "🏋️ <b>FitCoach Bot — Meniu Principal</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nCe dorești să gestionezi astăzi?",
        "clients_menu": "👤 <b>Gestionare Clienți</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nClienți activi: <b>{count} / {max}</b>\n\nAdaugă, editează, elimină clienți sau vizualizează lista completă.",
        "no_clients": "👤 <b>Niciun client încă.</b>\n\nAdaugă primul client pentru a începe.",
        "max_clients": "⚠️ <b>Limită atinsă ({max} clienți).</b>\n\nElimină un client existent înainte de a adăuga unul nou.",
        "client_added": "✅ <b>{name}</b> a fost adăugat în lista ta.",
        "client_updated": "✅ Profilul <b>{name}</b> a fost actualizat cu succes.",
        "confirm_del_client": "⚠️ <b>Elimină Client</b>\n\nElimini <b>{name}</b> din lista ta?\n\n<i>Toate sesiunile și planurile sale vor fi șterse. Această acțiune nu poate fi anulată.</i>",
        "client_deleted": "✅ <b>{name}</b> a fost eliminat din lista ta.",
        "schedule_menu": "📅 <b>Program</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nVizualizează programul sau gestionează sesiunile.",
        "no_clients_for_session": "⚠️ Niciun client în lista ta.\n\nAdaugă cel puțin un client înainte de a programa o sesiune.",
        "session_added": "✅ <b>Sesiune Programată</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n👤 Client   : <b>{name}</b>\n📅 Data     : {date}\n⏱ Durată   : {duration} min\n\n<i>Vei primi un memento cu 1h și 2h înainte de sesiune.</i>",
        "session_updated": "✅ Sesiunea pentru <b>{name}</b> a fost actualizată.",
        "confirm_del_session": "⚠️ <b>Anulează Sesiunea</b>\n\nAnulezi sesiunea cu <b>{name}</b>\ndin {date}?\n\n<i>Această acțiune nu poate fi anulată.</i>",
        "session_deleted": "✅ Sesiunea a fost eliminată din program.",
        "reminder": "🔔 <b>Memento Sesiune</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ <b>{hours} oră{plural}</b> până la sesiunea cu:\n\n👤 <b>{name}</b>\n🕐 {time}  •  {duration} min",
        "workout_menu": "📋 <b>Planuri de Antrenament</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nCreează și gestionează planuri personalizate pentru fiecare client.",
        "plan_added": "✅ <b>Plan Salvat</b>\n\n👤 Client : <b>{name}</b>\n📋 Plan   : {title}",
        "no_plans": "Nu s-au găsit planuri de antrenament.",
        "cancelled": "Operație anulată.",
        "deletion_cancelled": "Ștergere anulată.",
        "client_not_found": "Clientul nu a fost găsit.",
        "no_upcoming": "Nu există sesiuni viitoare.",
        "no_sessions_edit": "Nu există sesiuni viitoare de editat.",
        "no_sessions_all": "Nu s-au găsit sesiuni.",
        "history_empty": "Niciun istoric încă.",
        "pkg_month_prompt": "Introdu luna pentru acest pachet:\n<code>Format: MM/YYYY  (ex: 06/2025)</code>",
        "pkg_bought_prompt": "Câte ședințe a cumpărat <b>{name}</b> pentru {month}?",
        "pkg_used_prompt": "Câte ședințe a folosit <b>{name}</b> până acum în {month}?\n<i>(Scrie 0 dacă niciuna)</i>",
        "pkg_saved": "✅ Pachet salvat: <b>{name}</b> — {month}\n📦 Cumpărate: {bought}  |  ✅ Folosite: {used}  |  🔄 Rămase: {left}",
        "pkg_menu": "📦 <b>Pachete Ședințe</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nGestionează pachetele lunare de ședințe per client.",
        "pkg_none": "Nu s-au găsit pachete pentru acest client.",
        "sessions_left": "ședințe rămase",
        "of": "din",
        "free": "Liber",
        "no_sessions_day": "Nicio sesiune programată.",
        "total": "Total",
        "session_s": "ședință",
        "sessions_s": "ședințe",
        "this_month": "în această lună",
        "joined": "Înregistrat",
        "next": "Următor",
        "btn_clients": "👤  Clienți",
        "btn_schedule": "📅  Program",
        "btn_plans": "📋  Planuri",
        "btn_add_client": "➕  Adaugă Client",
        "btn_edit_client": "✏️  Editează Client",
        "btn_del_client": "🗑  Elimină Client",
        "btn_view_all": "📋  Vezi Toți",
        "btn_history": "🕑  Istoric",
        "btn_main_menu": "↩  Meniu Principal",
        "btn_today": "📅  Azi",
        "btn_week": "📆  Săptămâna",
        "btn_month": "🗓  Luna",
        "btn_all_sess": "📋  Toate Sesiunile",
        "btn_add_sess": "➕  Adaugă Sesiune",
        "btn_edit_sess": "✏️  Editează Sesiune",
        "btn_del_sess": "🗑  Anulează Sesiune",
        "btn_new_plan": "➕  Plan Nou",
        "btn_all_plans": "📋  Toate Planurile",
        "btn_plans_by": "👤  Planuri per Client",
        "btn_pkg": "📦  Pachete",
        "btn_add_pkg": "➕  Adaugă Pachet",
        "btn_view_pkg": "📊  Vezi Pachete",
        "btn_edit_used": "✏️  Actualizează Folosite",
        "btn_confirm": "✅  Confirmă",
        "btn_cancel": "✖  Anulează",
        "btn_back": "↩  Înapoi",
        "select_client": "Selectează un client:",
        "select_edit_field": "Ce dorești să editezi?",
        "enter_name": "➕ <b>Client Nou</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nIntrodu numele complet al clientului:",
        "enter_phone": "Introdu numărul de telefon:\n<i>(Scrie <code>skip</code> pentru a lăsa gol)</i>",
        "enter_notes": "Note despre acest client?\n<i>ex: accidentări, obiective, preferințe\n(Scrie <code>skip</code> pentru a lăsa gol)</i>",
        "field_name": "nume complet", "field_phone": "număr de telefon", "field_notes": "note",
        "field_sessions_bought": "ședințe cumpărate luna aceasta",
        "field_sessions_used": "ședințe folosite luna aceasta",
        "enter_field": "Introdu noul <b>{label}</b>:\n<i>(Scrie <code>skip</code> pentru a șterge)</i>",
        "enter_field_num": "Introdu noul <b>{label}</b>:\n<i>(Introdu un număr, ex: 8)</i>",
        "invalid_date": "⚠️ Format invalid. Folosește ZZ/LL/AAAA:",
        "invalid_time": "⚠️ Format invalid. Folosește HH:MM (ex: 09:30):",
        "invalid_duration": "⚠️ Introdu un număr valid de minute (ex: 60):",
        "invalid_number": "⚠️ Introdu un număr valid:",
        "past_date": "⚠️ Data este în trecut. Introdu o dată viitoare (ZZ/LL/AAAA):",
        "date_prompt": "Introdu data:\n<code>Format: ZZ/LL/AAAA  (ex: 25/06/2025)</code>",
        "time_prompt": "Introdu ora de start:\n<code>Format: HH:MM  (ex: 09:30)</code>",
        "duration_prompt": "Durata sesiunii în minute:\n<code>ex: 60</code>",
        "notes_prompt": "Note sesiune:\n<i>(Scrie <code>skip</code> pentru a lăsa gol)</i>",
        "roster_title": "<b>👤 Listă Clienți</b>\n",
        "history_title": "<b>🕑 Istoric Clienți</b>\n",
        "all_sessions_title": "<b>📋 Toate Sesiunile</b>\n",
        "editing_session": "<b>✏️ Editare Sesiune</b>\n\n👤 {name}\n📅 {date}\n⏱ {duration} min\n📝 {notes}\n\nCe dorești să modifici?",
        "editing_client": "<b>✏️ Editare: {name}</b>\n\n📞 Telefon : {phone}\n📝 Note : {notes}\n📦 Ședințe cumpărate : {bought}\n✅ Ședințe folosite  : {used}\n\nCe dorești să editezi?",
        "del_hist_btn": "🗑 Șterge: {name} ({date})",
        "week_of": "Săptămâna",
        "select_sess_edit": "<b>✏️ Editează Sesiunea</b>\n\nSelectează sesiunea de editat:",
        "select_sess_del": "<b>🗑 Anulează Sesiunea</b>\n\nSelectează sesiunea de eliminat:",
        "plan_title_prompt": "Introdu titlul planului:\n<i>ex: Săptămâna 1 — Forță</i>",
        "plan_content_prompt": "<b>📋 Conținut Plan</b>\n\nIntrodu planul complet de antrenament:\n\n<code>Ziua 1 — Împins\nFloating 4×8\nPrese umeri 3×10\n\nZiua 2 — Tras\nDeadlift 4×5\nTracțiuni 3×12</code>",
        "view_plan_title": "<b>📋 Vezi Plan</b>\n\nSelectează un client:",
        "invalid_month": "⚠️ Format invalid. Folosește LL/AAAA (ex: 06/2025):",
        "pkg_update_used_prompt": "Introdu noul număr de <b>ședințe folosite</b> pentru {name} în {month}:",
        "pkg_not_found": "Nu s-a găsit niciun pachet pentru această lună.",
        "language_prompt": "🌍 <b>Choose your language / Alege limba</b>",
        # ── Parametri corporali ──
        "body_menu": "📏 <b>Parametri Corporali</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nMonitorizează parametrii corporali pentru fiecare client.",
        "btn_body": "📏  Parametri Corporali",
        "btn_add_body": "➕  Adaugă Măsurătoare",
        "btn_view_body": "📊  Vezi Istoric",
        "btn_edit_body": "✏️  Editează Intrare",
        "btn_del_body": "🗑  Șterge Intrare",
        "body_select_client": "Selectează un client pentru parametri corporali:",
        "body_date_prompt": "Introdu data măsurătorii:\n<code>Format: ZZ/LL/AAAA</code>",
        "body_weight_prompt": "⚖️ Greutate (kg):\n<i>(ex: 75.5 — scrie <code>skip</code> pentru a sări)</i>",
        "body_chest_prompt": "📏 Diametru Piept (cm):\n<i>(scrie <code>skip</code> pentru a sări)</i>",
        "body_waist_prompt": "📏 Diametru Talie (cm):\n<i>(scrie <code>skip</code> pentru a sări)</i>",
        "body_hips_prompt": "📏 Diametru Bazin (cm):\n<i>(scrie <code>skip</code> pentru a sări)</i>",
        "body_leg_prompt": "📏 Diametru Picior (cm):\n<i>(scrie <code>skip</code> pentru a sări)</i>",
        "body_arm_prompt": "📏 Diametru Mâini (cm):\n<i>(scrie <code>skip</code> pentru a sări)</i>",
        "body_saved": "✅ Parametrii salvați pentru <b>{name}</b> pe data de {date}",
        "body_none": "Nu există măsurători înregistrate pentru acest client.",
        "body_updated": "✅ Intrarea a fost actualizată.",
        "body_deleted": "✅ Intrarea a fost ștearsă.",
        "body_select_entry": "Selectează o intrare pentru a o {action}:",
        "body_confirm_delete": "⚠️ Ștergi măsurătoarea din <b>{date}</b> pentru <b>{name}</b>?\n\nAceastă acțiune nu poate fi anulată.",
        "invalid_decimal": "⚠️ Introdu un număr valid (ex: 75.5) sau <code>skip</code>:",
        "body_edit_field_prompt": "Ce dorești să editezi?",
        "lbl_weight": "⚖️ Greutate",
        "lbl_chest": "📏 Piept",
        "lbl_waist": "📏 Talie",
        "lbl_hips": "📏 Bazin",
        "lbl_leg": "📏 Picior",
        "lbl_arm": "📏 Mâini",
        "unit_kg": "kg",
        "unit_cm": "cm",
    }
}

def t(lang, key, **kwargs):
    txt = T.get(lang, T["EN"]).get(key, T["EN"].get(key, key))
    if kwargs:
        try: txt = txt.format(**kwargs)
        except: pass
    return txt

def get_lang(context) -> str:
    return context.user_data.get("lang", "EN")

def fmt_date(d, time_str=None, lang="EN"):
    """Format: Luni / 25 Iunie / 09:30  or  Monday / 25 June / 09:30"""
    if isinstance(d, str):
        try: d = datetime.strptime(d, "%Y-%m-%d").date()
        except: return str(d)
    dow = d.weekday()
    day_name = (DAYS_RO if lang=="RO" else DAYS_EN)[dow]
    month_name = (MONTHS_RO if lang=="RO" else MONTHS_EN)[d.month]
    base = f"{day_name} / {d.day:02d} {month_name}"
    if time_str:
        return f"{base} / {time_str}"
    return base


# ═══════════════════════════════════════════════════════════════════
#  DATABASE
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT, notes TEXT,
                sessions_bought INTEGER DEFAULT 0,
                sessions_used   INTEGER DEFAULT 0,
                pkg_month       TEXT DEFAULT '',
                created_at TEXT DEFAULT (date('now'))
            );
            CREATE TABLE IF NOT EXISTS client_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL, client_name TEXT NOT NULL,
                phone TEXT, notes TEXT, action_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                session_date TEXT NOT NULL, session_time TEXT NOT NULL,
                duration INTEGER NOT NULL DEFAULT 60, notes TEXT,
                reminded_1h INTEGER DEFAULT 0, reminded_2h INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS session_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                pkg_month TEXT NOT NULL,
                sessions_bought INTEGER DEFAULT 0,
                sessions_used   INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS workout_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                title TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT DEFAULT (date('now'))
            );
            CREATE TABLE IF NOT EXISTS trainer_chat (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS body_measurements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                meas_date   TEXT    NOT NULL,
                weight      REAL,
                chest       REAL,
                waist       REAL,
                hips        REAL,
                leg         REAL,
                arm         REAL,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        # migrate existing clients table if columns missing
        try:
            self.conn.execute("ALTER TABLE clients ADD COLUMN sessions_bought INTEGER DEFAULT 0")
            self.conn.execute("ALTER TABLE clients ADD COLUMN sessions_used INTEGER DEFAULT 0")
            self.conn.execute("ALTER TABLE clients ADD COLUMN pkg_month TEXT DEFAULT ''")
            self.conn.commit()
        except: pass
        self.conn.commit()

    def set_trainer_chat(self, chat_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trainer_chat")
        cur.execute("INSERT INTO trainer_chat (id, chat_id) VALUES (1, ?)", (chat_id,))
        self.conn.commit()

    def get_trainer_chat(self):
        row = self.conn.execute("SELECT chat_id FROM trainer_chat WHERE id=1").fetchone()
        return row["chat_id"] if row else None

    # ── Clients ───────────────────────────────────────────────────
    def get_all_clients(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM clients ORDER BY name").fetchall()]

    def get_client(self, cid):
        row = self.conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        return dict(row) if row else None

    def add_client(self, name, phone, notes, sessions_bought=0, sessions_used=0, pkg_month=""):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO clients (name, phone, notes, sessions_bought, sessions_used, pkg_month) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, phone, notes, sessions_bought, sessions_used, pkg_month))
        self.conn.commit()
        self._log_history("ADDED", name, phone, notes)
        return cur.lastrowid

    def update_client(self, cid, name, phone, notes, sessions_bought=None, sessions_used=None, pkg_month=None):
        c = self.get_client(cid)
        sb = sessions_bought if sessions_bought is not None else c.get("sessions_bought", 0)
        su = sessions_used   if sessions_used   is not None else c.get("sessions_used", 0)
        pm = pkg_month       if pkg_month       is not None else c.get("pkg_month", "")
        self.conn.execute("UPDATE clients SET name=?, phone=?, notes=?, sessions_bought=?, sessions_used=?, pkg_month=? WHERE id=?",
                          (name, phone, notes, sb, su, pm, cid))
        self.conn.commit()

    def delete_client(self, cid):
        c = self.get_client(cid)
        if c: self._log_history("DELETED", c["name"], c.get("phone",""), c.get("notes",""))
        self.conn.execute("DELETE FROM clients WHERE id=?", (cid,))
        self.conn.commit()

    def get_next_session_for_client(self, cid):
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT session_date, session_time FROM sessions WHERE client_id=? AND session_date >= ? ORDER BY session_date, session_time LIMIT 1",
            (cid, today)).fetchone()
        return (row["session_date"], row["session_time"]) if row else None

    def _log_history(self, action, name, phone, notes):
        self.conn.execute("INSERT INTO client_history (action, client_name, phone, notes) VALUES (?, ?, ?, ?)",
                          (action, name, phone or "", notes or ""))
        self.conn.commit()

    def get_history(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM client_history ORDER BY action_at DESC").fetchall()]

    def delete_history_entry(self, entry_id):
        self.conn.execute("DELETE FROM client_history WHERE id=?", (entry_id,))
        self.conn.commit()

    # ── Session Packages ──────────────────────────────────────────
    def upsert_package(self, client_id, pkg_month, sessions_bought, sessions_used):
        row = self.conn.execute("SELECT id FROM session_packages WHERE client_id=? AND pkg_month=?", (client_id, pkg_month)).fetchone()
        if row:
            self.conn.execute("UPDATE session_packages SET sessions_bought=?, sessions_used=? WHERE id=?",
                              (sessions_bought, sessions_used, row["id"]))
        else:
            self.conn.execute("INSERT INTO session_packages (client_id, pkg_month, sessions_bought, sessions_used) VALUES (?, ?, ?, ?)",
                              (client_id, pkg_month, sessions_bought, sessions_used))
        self.conn.commit()

    def get_packages_for_client(self, client_id):
        rows = self.conn.execute("SELECT * FROM session_packages WHERE client_id=? ORDER BY pkg_month DESC", (client_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_package(self, client_id, pkg_month):
        row = self.conn.execute("SELECT * FROM session_packages WHERE client_id=? AND pkg_month=?", (client_id, pkg_month)).fetchone()
        return dict(row) if row else None

    def get_current_package(self, client_id):
        cur_month = date.today().strftime("%m/%Y")
        return self.get_package(client_id, cur_month)

    # ── Sessions ──────────────────────────────────────────────────
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
            "SELECT s.*, c.name AS client_name FROM sessions s JOIN clients c ON c.id=s.client_id ORDER BY s.session_date ASC, s.session_time ASC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, sid):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.conn.commit()

    def get_sessions_needing_reminder(self, hours_before):
        now = datetime.now(); target = now + timedelta(hours=hours_before)
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
        self.conn.commit(); return cur.lastrowid

    def get_plans_for_client(self, client_id):
        rows = self.conn.execute("SELECT * FROM workout_plans WHERE client_id=? ORDER BY created_at DESC", (client_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Body Measurements ─────────────────────────────────────────
    def add_body_measurement(self, client_id, meas_date, weight, chest, waist, hips, leg, arm):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO body_measurements (client_id, meas_date, weight, chest, waist, hips, leg, arm) VALUES (?,?,?,?,?,?,?,?)",
            (client_id, meas_date, weight, chest, waist, hips, leg, arm))
        self.conn.commit()
        return cur.lastrowid

    def get_body_measurements(self, client_id):
        rows = self.conn.execute(
            "SELECT * FROM body_measurements WHERE client_id=? ORDER BY meas_date ASC, created_at ASC",
            (client_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_body_measurement(self, mid):
        row = self.conn.execute("SELECT * FROM body_measurements WHERE id=?", (mid,)).fetchone()
        return dict(row) if row else None

    def update_body_measurement(self, mid, meas_date, weight, chest, waist, hips, leg, arm):
        self.conn.execute(
            "UPDATE body_measurements SET meas_date=?, weight=?, chest=?, waist=?, hips=?, leg=?, arm=? WHERE id=?",
            (meas_date, weight, chest, waist, hips, leg, arm, mid))
        self.conn.commit()

    def delete_body_measurement(self, mid):
        self.conn.execute("DELETE FROM body_measurements WHERE id=?", (mid,))
        self.conn.commit()


# ═══════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════════
def main_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_clients"), callback_data="clients_menu"),
         InlineKeyboardButton(t(lang,"btn_schedule"), callback_data="schedule_menu")],
        [InlineKeyboardButton(t(lang,"btn_plans"), callback_data="workout_menu")],
        [InlineKeyboardButton("🌍 EN / RO", callback_data="change_lang")],
    ])

def clients_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_add_client"), callback_data="add_client"),
         InlineKeyboardButton(t(lang,"btn_edit_client"), callback_data="edit_client_start")],
        [InlineKeyboardButton(t(lang,"btn_del_client"), callback_data="delete_client"),
         InlineKeyboardButton(t(lang,"btn_view_all"), callback_data="list_clients")],
        [InlineKeyboardButton(t(lang,"btn_history"), callback_data="client_history"),
         InlineKeyboardButton(t(lang,"btn_pkg"), callback_data="pkg_menu")],
        [InlineKeyboardButton(t(lang,"btn_body"), callback_data="body_menu")],
        [InlineKeyboardButton(t(lang,"btn_main_menu"), callback_data="main_menu")],
    ])

def schedule_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_today"), callback_data="view_today"),
         InlineKeyboardButton(t(lang,"btn_week"), callback_data="view_weekly"),
         InlineKeyboardButton(t(lang,"btn_month"), callback_data="view_monthly")],
        [InlineKeyboardButton(t(lang,"btn_all_sess"), callback_data="view_all_sessions")],
        [InlineKeyboardButton(t(lang,"btn_add_sess"), callback_data="add_session"),
         InlineKeyboardButton(t(lang,"btn_edit_sess"), callback_data="edit_session_start")],
        [InlineKeyboardButton(t(lang,"btn_del_sess"), callback_data="delete_session")],
        [InlineKeyboardButton(t(lang,"btn_main_menu"), callback_data="main_menu")],
    ])

def workout_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_new_plan"), callback_data="add_plan"),
         InlineKeyboardButton(t(lang,"btn_all_plans"), callback_data="list_plans")],
        [InlineKeyboardButton(t(lang,"btn_plans_by"), callback_data="view_client_plan")],
        [InlineKeyboardButton(t(lang,"btn_main_menu"), callback_data="main_menu")],
    ])

def body_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_add_body"), callback_data="body_add_start"),
         InlineKeyboardButton(t(lang,"btn_view_body"), callback_data="body_view_start")],
        [InlineKeyboardButton(t(lang,"btn_edit_body"), callback_data="body_edit_start"),
         InlineKeyboardButton(t(lang,"btn_del_body"), callback_data="body_del_start")],
        [InlineKeyboardButton(t(lang,"btn_back"), callback_data="clients_menu")],
    ])

def pkg_menu_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang,"btn_add_pkg"), callback_data="add_pkg_start"),
         InlineKeyboardButton(t(lang,"btn_view_pkg"), callback_data="view_pkg_start")],
        [InlineKeyboardButton(t(lang,"btn_edit_used"), callback_data="edit_pkg_used_start")],
        [InlineKeyboardButton(t(lang,"btn_back"), callback_data="clients_menu")],
    ])

def confirm_keyboard(lang, confirm_data, cancel_data):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang,"btn_confirm"), callback_data=confirm_data),
        InlineKeyboardButton(t(lang,"btn_cancel"), callback_data=cancel_data),
    ]])

def client_list_keyboard(clients, prefix, lang):
    rows = [[InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")] for c in clients]
    rows.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

def language_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:EN"),
        InlineKeyboardButton("🇷🇴 Română",  callback_data="set_lang:RO"),
    ]])


# ═══════════════════════════════════════════════════════════════════
#  SCHEDULER
# ═══════════════════════════════════════════════════════════════════
async def reminder_loop(app, db):
    while True:
        try:
            chat_id = db.get_trainer_chat()
            if chat_id:
                for hours in REMINDER_HOURS:
                    for s in db.get_sessions_needing_reminder(hours):
                        await app.bot.send_message(chat_id=chat_id, parse_mode="HTML",
                            text=f"🔔 <b>Session Reminder</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ <b>{hours}h</b> until session with:\n\n👤 <b>{s['client_name']}</b>\n🕐 {s['session_time']}  •  {s['duration']} min")
                        db.mark_reminded(s["id"], hours)
        except Exception as exc:
            logger.error("Reminder error: %s", exc)
        await asyncio.sleep(60)

def setup_scheduler(app, db):
    async def _start(application):
        asyncio.create_task(reminder_loop(application, db))
    app.post_init = _start


# ═══════════════════════════════════════════════════════════════════
#  CONVERSATION STATES
# ═══════════════════════════════════════════════════════════════════
(ADD_CLIENT_NAME, ADD_CLIENT_PHONE, ADD_CLIENT_NOTES, ADD_CLIENT_PKG_MONTH, ADD_CLIENT_PKG_BOUGHT, ADD_CLIENT_PKG_USED,
 EDIT_CLIENT_SELECT, EDIT_CLIENT_FIELD, EDIT_CLIENT_VALUE,
 ADD_SESSION_CLIENT, ADD_SESSION_DATE, ADD_SESSION_TIME, ADD_SESSION_DURATION, ADD_SESSION_NOTES,
 EDIT_SESSION_SELECT, EDIT_SESSION_FIELD, EDIT_SESSION_VALUE,
 ADD_PLAN_CLIENT, ADD_PLAN_TITLE, ADD_PLAN_CONTENT,
 CONFIRM_DELETE_CLIENT, CONFIRM_DELETE_SESSION,
 PKG_SELECT_CLIENT, PKG_ENTER_MONTH, PKG_ENTER_BOUGHT, PKG_ENTER_USED,
 PKG_EDIT_SELECT_CLIENT, PKG_EDIT_SELECT_MONTH, PKG_EDIT_ENTER_USED,
 BODY_SELECT_CLIENT, BODY_DATE, BODY_WEIGHT, BODY_CHEST, BODY_WAIST, BODY_HIPS, BODY_LEG, BODY_ARM,
 BODY_EDIT_SELECT_CLIENT, BODY_EDIT_SELECT_ENTRY, BODY_EDIT_FIELD, BODY_EDIT_VALUE,
 BODY_DEL_SELECT_CLIENT, BODY_DEL_SELECT_ENTRY, BODY_DEL_CONFIRM) = range(44)


# ═══════════════════════════════════════════════════════════════════
#  FORMATTERS
# ═══════════════════════════════════════════════════════════════════
def fmt_daily(day, sessions, lang):
    month_name = (MONTHS_RO if lang=="RO" else MONTHS_EN)[day.month]
    dow = (DAYS_RO if lang=="RO" else DAYS_EN)[day.weekday()]
    h = f"<b>📅 {dow} / {day.day:02d} {month_name} / {day.year}</b>\n" + "─"*28 + "\n\n"
    if not sessions: return h + f"<i>{t(lang,'no_sessions_day')}</i>"
    body = ""
    for s in sorted(sessions, key=lambda x: x["session_time"]):
        body += f"🕐 <b>{s['session_time']}</b>  {s['client_name']}  <i>({s['duration']} min)</i>\n"
        if s.get("notes"): body += f"   📝 {s['notes']}\n"
        body += "\n"
    return h + body

def fmt_weekly(monday, week, lang):
    month_name = (MONTHS_RO if lang=="RO" else MONTHS_EN)[monday.month]
    txt = f"<b>📆 {t(lang,'week_of')} {monday.day:02d} {month_name}</b>\n" + "─"*28 + "\n\n"
    short = DAYS_SHORT_RO if lang=="RO" else DAYS_SHORT_EN
    for i, (d, sessions) in enumerate(week.items()):
        marker = "▶" if d == date.today() else "  "
        txt += f"{marker} <b>{short[i]} {d.strftime('%d/%m')}</b>\n"
        if sessions:
            for s in sorted(sessions, key=lambda x: x["session_time"]):
                txt += f"    {s['session_time']} — {s['client_name']} ({s['duration']}m)\n"
        else: txt += f"    <i>{t(lang,'free')}</i>\n"
        txt += "\n"
    return txt

def fmt_monthly(today, sessions, lang):
    month_name = (MONTHS_RO if lang=="RO" else MONTHS_EN)[today.month]
    txt = f"<b>🗓 {month_name} {today.year}</b>\n" + "─"*28 + "\n\n"
    by_day = {}
    for s in sessions: by_day.setdefault(s["session_date"], []).append(s)
    if not by_day: return txt + f"<i>{t(lang,'no_sessions_day')}</i>"
    short = DAYS_SHORT_RO if lang=="RO" else DAYS_SHORT_EN
    for d in sorted(by_day):
        day_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
        txt += f"{'▶ ' if day_obj==today else ''}<b>{short[day_obj.weekday()]} {day_obj.strftime('%d/%m')}</b>\n"
        for s in sorted(by_day[d], key=lambda x: x["session_time"]):
            txt += f"  {s['session_time']} {s['client_name']} ({s['duration']}m)\n"
        txt += "\n"
    total = sum(len(v) for v in by_day.values())
    sess_word = t(lang,"session_s") if total==1 else t(lang,"sessions_s")
    txt += f"<i>{t(lang,'total')}: {total} {sess_word} {t(lang,'this_month')}</i>"
    return txt

def pkg_bar(used, bought):
    if bought == 0: return "—"
    filled = min(used, bought)
    bar = "🟢" * filled + "⚪" * max(0, bought - filled)
    return bar

db = Database()


# ═══════════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════════

async def start(update, context):
    db.set_trainer_chat(update.effective_chat.id)
    await update.message.reply_text(t("EN","language_prompt"), reply_markup=language_keyboard(), parse_mode="HTML")

async def set_language(update, context):
    q = update.callback_query; await q.answer()
    lang = q.data.split(":")[1]
    context.user_data["lang"] = lang
    await q.edit_message_text(t(lang,"welcome",name=update.effective_user.first_name),
                               reply_markup=main_menu_keyboard(lang), parse_mode="HTML")

async def change_lang(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(t("EN","language_prompt"), reply_markup=language_keyboard(), parse_mode="HTML")

async def cmd_main_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"main_menu"), reply_markup=main_menu_keyboard(lang), parse_mode="HTML")

async def cmd_clients_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"clients_menu",count=len(db.get_all_clients()),max=MAX_CLIENTS),
                               reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")

async def cmd_list_clients(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML"); return
    txt = t(lang,"roster_title") + "─"*28 + "\n\n"
    for i, c in enumerate(clients, 1):
        ns = db.get_next_session_for_client(c["id"])
        pkg = db.get_current_package(c["id"])
        left = (pkg["sessions_bought"] - pkg["sessions_used"]) if pkg else 0
        bought = pkg["sessions_bought"] if pkg else 0
        txt += f"<b>{i:02d}. {c['name']}</b>\n"
        txt += f"   📞 {c['phone'] or '—'}\n"
        txt += f"   📝 {c['notes'] or '—'}\n"
        if pkg:
            txt += f"   📦 {pkg['pkg_month']}: {left} {t(lang,'sessions_left')} ({t(lang,'of')} {bought})\n"
            txt += f"   {pkg_bar(pkg['sessions_used'], pkg['sessions_bought'])}\n"
        if ns: txt += f"   ⏭ {t(lang,'next')}: <i>{fmt_date(ns[0], ns[1], lang)}</i>\n"
        txt += "\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")

# ── Add client ────────────────────────────────────────────────────
async def add_client_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    if len(db.get_all_clients()) >= MAX_CLIENTS:
        await q.edit_message_text(t(lang,"max_clients",max=MAX_CLIENTS), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(t(lang,"enter_name"), parse_mode="HTML")
    return ADD_CLIENT_NAME

async def add_client_name(update, context):
    context.user_data["nc"] = {"name": update.message.text.strip()}
    lang = get_lang(context)
    await update.message.reply_text(t(lang,"enter_phone"), parse_mode="HTML")
    return ADD_CLIENT_PHONE

async def add_client_phone(update, context):
    lang = get_lang(context); txt = update.message.text.strip()
    context.user_data["nc"]["phone"] = "" if txt.lower()=="skip" else txt
    await update.message.reply_text(t(lang,"enter_notes"), parse_mode="HTML")
    return ADD_CLIENT_NOTES

async def add_client_notes(update, context):
    lang = get_lang(context); d = context.user_data["nc"]
    d["notes"] = "" if update.message.text.strip().lower()=="skip" else update.message.text.strip()
    await update.message.reply_text(t(lang,"pkg_month_prompt"), parse_mode="HTML")
    return ADD_CLIENT_PKG_MONTH

async def add_client_pkg_month(update, context):
    lang = get_lang(context); txt = update.message.text.strip()
    if txt.lower() == "skip":
        context.user_data["nc"]["pkg_month"] = ""
        cid = db.add_client(context.user_data["nc"]["name"], context.user_data["nc"]["phone"], context.user_data["nc"]["notes"])
        await update.message.reply_text(t(lang,"client_added",name=context.user_data["nc"]["name"]),
                                         reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    try:
        datetime.strptime(txt, "%m/%Y")
        context.user_data["nc"]["pkg_month"] = txt
        await update.message.reply_text(
            t(lang,"pkg_bought_prompt", name=context.user_data["nc"]["name"], month=txt), parse_mode="HTML")
        return ADD_CLIENT_PKG_BOUGHT
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_month"), parse_mode="HTML")
        return ADD_CLIENT_PKG_MONTH

async def add_client_pkg_bought(update, context):
    lang = get_lang(context)
    try:
        bought = int(update.message.text.strip())
        if bought < 0: raise ValueError
        context.user_data["nc"]["pkg_bought"] = bought
        await update.message.reply_text(
            t(lang,"pkg_used_prompt", name=context.user_data["nc"]["name"], month=context.user_data["nc"]["pkg_month"]),
            parse_mode="HTML")
        return ADD_CLIENT_PKG_USED
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
        return ADD_CLIENT_PKG_BOUGHT

async def add_client_pkg_used(update, context):
    lang = get_lang(context)
    try:
        used = int(update.message.text.strip())
        if used < 0: raise ValueError
        d = context.user_data["nc"]
        cid = db.add_client(d["name"], d["phone"], d["notes"])
        db.upsert_package(cid, d["pkg_month"], d["pkg_bought"], used)
        left = d["pkg_bought"] - used
        await update.message.reply_text(
            t(lang,"pkg_saved", name=d["name"], month=d["pkg_month"], bought=d["pkg_bought"], used=used, left=left),
            reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
        return ADD_CLIENT_PKG_USED

# ── Edit client ───────────────────────────────────────────────────
async def edit_client_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>✏️</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"editcl",lang), parse_mode="HTML")
    return EDIT_CLIENT_SELECT

async def edit_client_select(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["edit_cid"] = cid
    pkg = db.get_current_package(cid)
    bought = pkg["sessions_bought"] if pkg else 0
    used = pkg["sessions_used"] if pkg else 0
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 " + t(lang,"field_name"), callback_data="editcl_field:name"),
         InlineKeyboardButton("📞 " + t(lang,"field_phone"), callback_data="editcl_field:phone")],
        [InlineKeyboardButton("📝 " + t(lang,"field_notes"), callback_data="editcl_field:notes")],
        [InlineKeyboardButton("📦 " + t(lang,"field_sessions_bought"), callback_data="editcl_field:sessions_bought")],
        [InlineKeyboardButton("✅ " + t(lang,"field_sessions_used"), callback_data="editcl_field:sessions_used")],
        [InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="clients_menu")],
    ])
    await q.edit_message_text(
        t(lang,"editing_client", name=c["name"], phone=c.get("phone") or "—", notes=c.get("notes") or "—", bought=bought, used=used),
        reply_markup=kb, parse_mode="HTML")
    return EDIT_CLIENT_FIELD

async def edit_client_field(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    field = q.data.split(":")[1]; context.user_data["edit_cl_field"] = field
    if field in ("sessions_bought","sessions_used"):
        label = t(lang, f"field_{field}")
        await q.edit_message_text(t(lang,"enter_field_num",label=label), parse_mode="HTML")
    else:
        label = t(lang, f"field_{field}")
        await q.edit_message_text(t(lang,"enter_field",label=label), parse_mode="HTML")
    return EDIT_CLIENT_VALUE

async def edit_client_value(update, context):
    lang = get_lang(context)
    cid = context.user_data["edit_cid"]; field = context.user_data["edit_cl_field"]
    txt = update.message.text.strip(); c = db.get_client(cid)
    if field in ("sessions_bought","sessions_used"):
        try:
            val = int(txt)
            if val < 0: raise ValueError
            pkg = db.get_current_package(cid)
            cur_month = date.today().strftime("%m/%Y")
            if pkg:
                bought = val if field=="sessions_bought" else pkg["sessions_bought"]
                used   = val if field=="sessions_used"   else pkg["sessions_used"]
                db.upsert_package(cid, pkg["pkg_month"], bought, used)
            else:
                bought = val if field=="sessions_bought" else 0
                used   = val if field=="sessions_used"   else 0
                db.upsert_package(cid, cur_month, bought, used)
            await update.message.reply_text(t(lang,"client_updated",name=c["name"]),
                                             reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
            return EDIT_CLIENT_VALUE
    else:
        value = "" if txt.lower()=="skip" else txt
        updated = {k: c[k] for k in ("name","phone","notes")}; updated[field] = value
        db.update_client(cid, updated["name"], updated["phone"], updated["notes"])
        await update.message.reply_text(t(lang,"client_updated",name=updated["name"]),
                                         reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END

# ── Delete client ─────────────────────────────────────────────────
async def delete_client_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>🗑</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"del_client",lang), parse_mode="HTML")
    return CONFIRM_DELETE_CLIENT

async def confirm_delete_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    if not c:
        await q.edit_message_text(t(lang,"client_not_found"), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    context.user_data["del_cid"] = cid
    await q.edit_message_text(t(lang,"confirm_del_client",name=c["name"]),
                               reply_markup=confirm_keyboard(lang,"confirm_del_client","cancel_del_client"), parse_mode="HTML")
    return CONFIRM_DELETE_CLIENT

async def execute_delete_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    if q.data == "confirm_del_client":
        cid = context.user_data.get("del_cid"); c = db.get_client(cid); db.delete_client(cid)
        await q.edit_message_text(t(lang,"client_deleted",name=c["name"]), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
    else:
        await q.edit_message_text(t(lang,"deletion_cancelled"), reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

# ── History ───────────────────────────────────────────────────────
async def cmd_client_history(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    history = db.get_history()
    if not history:
        await q.edit_message_text(t(lang,"history_title") + "\n" + t(lang,"history_empty"),
                                   reply_markup=clients_menu_keyboard(lang), parse_mode="HTML"); return
    txt = t(lang,"history_title") + "─"*28 + "\n\n"; kb_rows = []
    for h in history:
        icon = "✅" if h["action"]=="ADDED" else "🗑"
        txt += f"{icon} <b>{h['client_name']}</b>  <i>{h['action_at'][:16]}</i>\n"
        if h.get("phone"): txt += f"   📞 {h['phone']}\n"
        if h.get("notes"): txt += f"   📝 {h['notes']}\n"
        txt += "\n"
        kb_rows.append([InlineKeyboardButton(t(lang,"del_hist_btn",name=h["client_name"],date=h["action_at"][:10]), callback_data=f"del_hist:{h['id']}")])
    kb_rows.append([InlineKeyboardButton(t(lang,"btn_back"), callback_data="clients_menu")])
    if len(txt) > 3800: txt = txt[:3790] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")

async def delete_history_entry(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    db.delete_history_entry(int(q.data.split(":")[1]))
    history = db.get_history()
    if not history:
        await q.edit_message_text(t(lang,"history_title") + "\n" + t(lang,"history_empty"),
                                   reply_markup=clients_menu_keyboard(lang), parse_mode="HTML"); return
    txt = t(lang,"history_title") + "─"*28 + "\n\n"; kb_rows = []
    for h in history:
        icon = "✅" if h["action"]=="ADDED" else "🗑"
        txt += f"{icon} <b>{h['client_name']}</b>  <i>{h['action_at'][:16]}</i>\n"
        if h.get("phone"): txt += f"   📞 {h['phone']}\n"
        if h.get("notes"): txt += f"   📝 {h['notes']}\n"
        txt += "\n"
        kb_rows.append([InlineKeyboardButton(t(lang,"del_hist_btn",name=h["client_name"],date=h["action_at"][:10]), callback_data=f"del_hist:{h['id']}")])
    kb_rows.append([InlineKeyboardButton(t(lang,"btn_back"), callback_data="clients_menu")])
    if len(txt) > 3800: txt = txt[:3790] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")

# ── Packages menu ─────────────────────────────────────────────────
async def cmd_pkg_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"pkg_menu"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")

# ── Add package ───────────────────────────────────────────────────
async def add_pkg_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>📦</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"pkgcl",lang), parse_mode="HTML")
    return PKG_SELECT_CLIENT

async def pkg_select_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["pkg_cid"] = cid; context.user_data["pkg_name"] = c["name"]
    await q.edit_message_text(t(lang,"pkg_month_prompt"), parse_mode="HTML")
    return PKG_ENTER_MONTH

async def pkg_enter_month(update, context):
    lang = get_lang(context); txt = update.message.text.strip()
    try:
        datetime.strptime(txt, "%m/%Y")
        context.user_data["pkg_month"] = txt
        await update.message.reply_text(
            t(lang,"pkg_bought_prompt", name=context.user_data["pkg_name"], month=txt), parse_mode="HTML")
        return PKG_ENTER_BOUGHT
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_month"), parse_mode="HTML")
        return PKG_ENTER_MONTH

async def pkg_enter_bought(update, context):
    lang = get_lang(context)
    try:
        bought = int(update.message.text.strip())
        if bought < 0: raise ValueError
        context.user_data["pkg_bought"] = bought
        await update.message.reply_text(
            t(lang,"pkg_used_prompt", name=context.user_data["pkg_name"], month=context.user_data["pkg_month"]),
            parse_mode="HTML")
        return PKG_ENTER_USED
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
        return PKG_ENTER_BOUGHT

async def pkg_enter_used(update, context):
    lang = get_lang(context)
    try:
        used = int(update.message.text.strip())
        if used < 0: raise ValueError
        cid = context.user_data["pkg_cid"]; name = context.user_data["pkg_name"]
        month = context.user_data["pkg_month"]; bought = context.user_data["pkg_bought"]
        db.upsert_package(cid, month, bought, used)
        left = bought - used
        await update.message.reply_text(
            t(lang,"pkg_saved", name=name, month=month, bought=bought, used=used, left=left),
            reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
        return PKG_ENTER_USED

# ── View packages ─────────────────────────────────────────────────
async def view_pkg_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML"); return
    await q.edit_message_text(f"<b>📊</b> {t(lang,'select_client')}",
                               reply_markup=client_list_keyboard(clients,"viewpkg",lang), parse_mode="HTML")

async def view_pkg_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    pkgs = db.get_packages_for_client(cid)
    if not pkgs:
        await q.edit_message_text(t(lang,"pkg_none"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML"); return
    txt = f"<b>📦 {c['name']}</b>\n" + "─"*28 + "\n\n"
    for p in pkgs:
        left = p["sessions_bought"] - p["sessions_used"]
        txt += f"📅 <b>{p['pkg_month']}</b>\n"
        txt += f"   📦 {t(lang,'of')} {p['sessions_bought']}  ✅ {p['sessions_used']}  🔄 {left} {t(lang,'sessions_left')}\n"
        txt += f"   {pkg_bar(p['sessions_used'], p['sessions_bought'])}\n\n"
    await q.edit_message_text(txt, reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")

# ── Edit used sessions ────────────────────────────────────────────
async def edit_pkg_used_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>✏️</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"editpkg",lang), parse_mode="HTML")
    return PKG_EDIT_SELECT_CLIENT

async def edit_pkg_select_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["epkg_cid"] = cid; context.user_data["epkg_name"] = c["name"]
    pkgs = db.get_packages_for_client(cid)
    if not pkgs:
        await q.edit_message_text(t(lang,"pkg_none"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{p['pkg_month']}  ({p['sessions_used']}/{p['sessions_bought']})", callback_data=f"editpkgm:{p['pkg_month']}")] for p in pkgs]
    kb.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="pkg_menu")])
    await q.edit_message_text(f"<b>✏️ {c['name']}</b>\n\nSelectează luna:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return PKG_EDIT_SELECT_MONTH

async def edit_pkg_select_month(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    month = q.data.split(":")[1]; context.user_data["epkg_month"] = month
    name = context.user_data["epkg_name"]
    await q.edit_message_text(t(lang,"pkg_update_used_prompt", name=name, month=month), parse_mode="HTML")
    return PKG_EDIT_ENTER_USED

async def edit_pkg_enter_used(update, context):
    lang = get_lang(context)
    try:
        used = int(update.message.text.strip())
        if used < 0: raise ValueError
        cid = context.user_data["epkg_cid"]; month = context.user_data["epkg_month"]
        pkg = db.get_package(cid, month)
        if not pkg:
            await update.message.reply_text(t(lang,"pkg_not_found"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
            return ConversationHandler.END
        db.upsert_package(cid, month, pkg["sessions_bought"], used)
        left = pkg["sessions_bought"] - used
        await update.message.reply_text(
            t(lang,"pkg_saved", name=context.user_data["epkg_name"], month=month,
              bought=pkg["sessions_bought"], used=used, left=left),
            reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_number"), parse_mode="HTML")
        return PKG_EDIT_ENTER_USED


# ── Schedule ──────────────────────────────────────────────────────
async def cmd_schedule_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"schedule_menu"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")

async def cmd_view_today(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    today = date.today()
    await q.edit_message_text(fmt_daily(today, db.get_sessions_for_date(today), lang),
                               reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")

async def cmd_view_weekly(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    today = date.today(); monday = today - timedelta(days=today.weekday())
    week = {monday + timedelta(days=i): db.get_sessions_for_date(monday + timedelta(days=i)) for i in range(7)}
    await q.edit_message_text(fmt_weekly(monday, week, lang), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")

async def cmd_view_monthly(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    today = date.today(); first_day = today.replace(day=1)
    last_day = (today.replace(year=today.year+1,month=1,day=1) if today.month==12 else today.replace(month=today.month+1,day=1)) - timedelta(days=1)
    await q.edit_message_text(fmt_monthly(today, db.get_sessions_for_range(first_day,last_day), lang),
                               reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")

async def cmd_view_all_sessions(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    sessions = db.get_all_sessions(limit=50)
    if not sessions:
        await q.edit_message_text(t(lang,"all_sessions_title") + "\n" + t(lang,"no_sessions_all"),
                                   reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML"); return
    txt = t(lang,"all_sessions_title") + "─"*28 + "\n\n"
    for s in sessions:
        txt += f"📅 <b>{fmt_date(s['session_date'], s['session_time'], lang)}</b>\n"
        txt += f"   👤 {s['client_name']}  ⏱ {s['duration']} min\n"
        if s.get("notes"): txt += f"   📝 {s['notes']}\n"
        txt += "\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")

# ── Add session ───────────────────────────────────────────────────
async def add_session_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients_for_session"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>📅</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"sess_client",lang), parse_mode="HTML")
    return ADD_SESSION_CLIENT

async def add_session_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); client = db.get_client(cid)
    context.user_data["ns"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(f"<b>📅 {client['name']}</b>\n\n{t(lang,'date_prompt')}", parse_mode="HTML")
    return ADD_SESSION_DATE

async def add_session_date(update, context):
    lang = get_lang(context)
    try:
        d = datetime.strptime(update.message.text.strip(), "%d/%m/%Y").date()
        if d < date.today():
            await update.message.reply_text(t(lang,"past_date"), parse_mode="HTML"); return ADD_SESSION_DATE
        context.user_data["ns"]["date"] = d
        await update.message.reply_text(t(lang,"time_prompt"), parse_mode="HTML")
        return ADD_SESSION_TIME
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_date"), parse_mode="HTML"); return ADD_SESSION_DATE

async def add_session_time(update, context):
    lang = get_lang(context)
    try:
        t_val = datetime.strptime(update.message.text.strip(), "%H:%M").time()
        context.user_data["ns"]["time"] = t_val
        await update.message.reply_text(t(lang,"duration_prompt"), parse_mode="HTML")
        return ADD_SESSION_DURATION
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_time"), parse_mode="HTML"); return ADD_SESSION_TIME

async def add_session_duration(update, context):
    lang = get_lang(context)
    try:
        dur = int(update.message.text.strip())
        if not (1 <= dur <= 300): raise ValueError
        context.user_data["ns"]["duration"] = dur
        await update.message.reply_text(t(lang,"notes_prompt"), parse_mode="HTML")
        return ADD_SESSION_NOTES
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_duration"), parse_mode="HTML"); return ADD_SESSION_DURATION

async def add_session_notes(update, context):
    lang = get_lang(context); txt = update.message.text.strip(); d = context.user_data["ns"]
    d["notes"] = "" if txt.lower()=="skip" else txt
    db.add_session(d["client_id"], d["date"], d["time"], d["duration"], d["notes"])
    await update.message.reply_text(
        t(lang,"session_added", name=d["client_name"],
          date=fmt_date(d["date"], d["time"].strftime("%H:%M"), lang), duration=d["duration"]),
        reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

# ── Edit session ──────────────────────────────────────────────────
async def edit_session_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await q.edit_message_text(t(lang,"no_sessions_edit"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{fmt_date(s['session_date'],s['session_time'],lang)} — {s['client_name']}", callback_data=f"editsess:{s['id']}")] for s in sessions]
    kb.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="schedule_menu")])
    await q.edit_message_text(t(lang,"select_sess_edit"), reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return EDIT_SESSION_SELECT

async def edit_session_select(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    sid = int(q.data.split(":")[1]); s = db.get_session(sid)
    context.user_data["edit_sid"] = sid
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 " + t(lang,"date_prompt")[:4], callback_data="editsess_field:date"),
         InlineKeyboardButton("🕐 " + t(lang,"time_prompt")[:4], callback_data="editsess_field:time")],
        [InlineKeyboardButton("⏱ " + t(lang,"duration_prompt")[:6], callback_data="editsess_field:duration"),
         InlineKeyboardButton("📝 Notes", callback_data="editsess_field:notes")],
        [InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="schedule_menu")],
    ])
    await q.edit_message_text(
        t(lang,"editing_session", name=s["client_name"],
          date=fmt_date(s["session_date"],s["session_time"],lang),
          duration=s["duration"], notes=s.get("notes") or "—"),
        reply_markup=kb, parse_mode="HTML")
    return EDIT_SESSION_FIELD

async def edit_session_field(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    field = q.data.split(":")[1]; context.user_data["edit_sess_field"] = field
    prompts = {"date": t(lang,"date_prompt"), "time": t(lang,"time_prompt"),
               "duration": t(lang,"duration_prompt"), "notes": t(lang,"notes_prompt")}
    await q.edit_message_text(prompts[field], parse_mode="HTML")
    return EDIT_SESSION_VALUE

async def edit_session_value(update, context):
    lang = get_lang(context)
    sid = context.user_data["edit_sid"]; field = context.user_data["edit_sess_field"]; txt = update.message.text.strip()
    s = db.get_session(sid)
    try:
        new_date = datetime.strptime(s["session_date"], "%Y-%m-%d").date()
        new_time = datetime.strptime(s["session_time"], "%H:%M").time()
        new_duration = s["duration"]; new_notes = s.get("notes") or ""
        if field == "date":
            new_date = datetime.strptime(txt, "%d/%m/%Y").date()
            if new_date < date.today():
                await update.message.reply_text(t(lang,"past_date"), parse_mode="HTML"); return EDIT_SESSION_VALUE
        elif field == "time": new_time = datetime.strptime(txt, "%H:%M").time()
        elif field == "duration":
            new_duration = int(txt)
            if not (1 <= new_duration <= 300): raise ValueError
        elif field == "notes": new_notes = "" if txt.lower()=="skip" else txt
        db.update_session(sid, new_date, new_time, new_duration, new_notes)
        await update.message.reply_text(t(lang,"session_updated",name=s["client_name"]),
                                         reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_date") if field=="date" else t(lang,"invalid_number"), parse_mode="HTML")
        return EDIT_SESSION_VALUE

# ── Delete session ────────────────────────────────────────────────
async def delete_session_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    sessions = db.get_upcoming_sessions(limit=20)
    if not sessions:
        await q.edit_message_text(t(lang,"no_upcoming"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{fmt_date(s['session_date'],s['session_time'],lang)} — {s['client_name']}", callback_data=f"del_sess:{s['id']}")] for s in sessions]
    kb.append([InlineKeyboardButton(t(lang,"btn_back"), callback_data="schedule_menu")])
    await q.edit_message_text(t(lang,"select_sess_del"), reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return CONFIRM_DELETE_SESSION

async def confirm_delete_session(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    sid = int(q.data.split(":")[1]); s = db.get_session(sid)
    context.user_data["del_sid"] = sid
    await q.edit_message_text(t(lang,"confirm_del_session", name=s["client_name"],
                                 date=fmt_date(s["session_date"],s["session_time"],lang)),
                               reply_markup=confirm_keyboard(lang,"confirm_del_sess","cancel_del_sess"), parse_mode="HTML")
    return CONFIRM_DELETE_SESSION

async def execute_delete_session(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    if q.data == "confirm_del_sess":
        db.delete_session(context.user_data.get("del_sid"))
        await q.edit_message_text(t(lang,"session_deleted"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
    else:
        await q.edit_message_text(t(lang,"deletion_cancelled"), reply_markup=schedule_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

# ── Workout plans ─────────────────────────────────────────────────
async def cmd_workout_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"workout_menu"), reply_markup=workout_menu_keyboard(lang), parse_mode="HTML")

async def cmd_list_plans(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients(); txt, any_plan = "<b>📋</b>\n" + "─"*28 + "\n\n", False
    for c in clients:
        plans = db.get_plans_for_client(c["id"])
        if plans:
            any_plan = True; txt += f"<b>👤 {c['name']}</b>\n"
            for p in plans: txt += f"  • {p['title']}  <i>({p['created_at']})</i>\n"
            txt += "\n"
    if not any_plan: txt += f"<i>{t(lang,'no_plans')}</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(lang), parse_mode="HTML")

async def add_plan_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=workout_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(f"<b>📋</b> {t(lang,'select_client')}", reply_markup=client_list_keyboard(clients,"plan_client",lang), parse_mode="HTML")
    return ADD_PLAN_CLIENT

async def add_plan_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); client = db.get_client(cid)
    context.user_data["np"] = {"client_id": cid, "client_name": client["name"]}
    await q.edit_message_text(f"<b>📋 {client['name']}</b>\n\n{t(lang,'plan_title_prompt')}", parse_mode="HTML")
    return ADD_PLAN_TITLE

async def add_plan_title(update, context):
    context.user_data["np"]["title"] = update.message.text.strip()
    lang = get_lang(context)
    await update.message.reply_text(t(lang,"plan_content_prompt"), parse_mode="HTML")
    return ADD_PLAN_CONTENT

async def add_plan_content(update, context):
    lang = get_lang(context); d = context.user_data["np"]; d["content"] = update.message.text.strip()
    db.add_plan(d["client_id"], d["title"], d["content"])
    await update.message.reply_text(t(lang,"plan_added",name=d["client_name"],title=d["title"]),
                                     reply_markup=workout_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

async def cmd_view_client_plan(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = [c for c in db.get_all_clients() if db.get_plans_for_client(c["id"])]
    if not clients:
        await q.edit_message_text(t(lang,"no_plans"), reply_markup=workout_menu_keyboard(lang), parse_mode="HTML"); return
    await q.edit_message_text(t(lang,"view_plan_title"), reply_markup=client_list_keyboard(clients,"view_plan",lang), parse_mode="HTML")

async def cmd_show_client_plans(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); client = db.get_client(cid); plans = db.get_plans_for_client(cid)
    if not plans:
        await q.edit_message_text(t(lang,"no_plans"), reply_markup=workout_menu_keyboard(lang), parse_mode="HTML"); return
    txt = f"<b>📋 {client['name']}</b>\n" + "─"*28 + "\n\n"
    for p in plans: txt += f"<b>{p['title']}</b>  <i>{p['created_at']}</i>\n{p['content']}\n\n" + "─"*20 + "\n\n"
    if len(txt) > 4000: txt = txt[:3990] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=workout_menu_keyboard(lang), parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
#  BODY MEASUREMENTS
# ══════════════════════════════════════════════════════════════════

def _fmt_body_entry(entry, lang):
    """Format a single body measurement entry."""
    d = entry.get("meas_date","")
    try:
        d_obj = datetime.strptime(d, "%Y-%m-%d").date()
        d_fmt = fmt_date(d_obj, None, lang)
    except:
        d_fmt = d
    lines = [f"📅 <b>{d_fmt}</b>"]
    if entry.get("weight") is not None:  lines.append(f"  {t(lang,'lbl_weight')}: {entry['weight']} {t(lang,'unit_kg')}")
    if entry.get("chest")  is not None:  lines.append(f"  {t(lang,'lbl_chest')}: {entry['chest']} {t(lang,'unit_cm')}")
    if entry.get("waist")  is not None:  lines.append(f"  {t(lang,'lbl_waist')}: {entry['waist']} {t(lang,'unit_cm')}")
    if entry.get("hips")   is not None:  lines.append(f"  {t(lang,'lbl_hips')}: {entry['hips']} {t(lang,'unit_cm')}")
    if entry.get("leg")    is not None:  lines.append(f"  {t(lang,'lbl_leg')}: {entry['leg']} {t(lang,'unit_cm')}")
    if entry.get("arm")    is not None:  lines.append(f"  {t(lang,'lbl_arm')}: {entry['arm']} {t(lang,'unit_cm')}")
    return "\n".join(lines)

def _parse_decimal(txt):
    """Return float or None; raise ValueError if invalid."""
    if txt.lower() == "skip":
        return None
    val = float(txt.replace(",","."))
    if val < 0: raise ValueError
    return val

async def cmd_body_menu(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    await q.edit_message_text(t(lang,"body_menu"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")

# ── Add measurement ───────────────────────────────────────────────
async def body_add_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(t(lang,"body_select_client"),
                               reply_markup=client_list_keyboard(clients,"bodyadd",lang), parse_mode="HTML")
    return BODY_SELECT_CLIENT

async def body_add_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["bm"] = {"cid": cid, "name": c["name"]}
    await q.edit_message_text(t(lang,"body_date_prompt"), parse_mode="HTML")
    return BODY_DATE

async def body_add_date(update, context):
    lang = get_lang(context)
    try:
        d = datetime.strptime(update.message.text.strip(), "%d/%m/%Y").date()
        context.user_data["bm"]["date"] = d.isoformat()
        await update.message.reply_text(t(lang,"body_weight_prompt"), parse_mode="HTML")
        return BODY_WEIGHT
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_date"), parse_mode="HTML")
        return BODY_DATE

async def body_add_weight(update, context):
    lang = get_lang(context)
    try:
        context.user_data["bm"]["weight"] = _parse_decimal(update.message.text.strip())
        await update.message.reply_text(t(lang,"body_chest_prompt"), parse_mode="HTML")
        return BODY_CHEST
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_WEIGHT

async def body_add_chest(update, context):
    lang = get_lang(context)
    try:
        context.user_data["bm"]["chest"] = _parse_decimal(update.message.text.strip())
        await update.message.reply_text(t(lang,"body_waist_prompt"), parse_mode="HTML")
        return BODY_WAIST
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_CHEST

async def body_add_waist(update, context):
    lang = get_lang(context)
    try:
        context.user_data["bm"]["waist"] = _parse_decimal(update.message.text.strip())
        await update.message.reply_text(t(lang,"body_hips_prompt"), parse_mode="HTML")
        return BODY_HIPS
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_WAIST

async def body_add_hips(update, context):
    lang = get_lang(context)
    try:
        context.user_data["bm"]["hips"] = _parse_decimal(update.message.text.strip())
        await update.message.reply_text(t(lang,"body_leg_prompt"), parse_mode="HTML")
        return BODY_LEG
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_HIPS

async def body_add_leg(update, context):
    lang = get_lang(context)
    try:
        context.user_data["bm"]["leg"] = _parse_decimal(update.message.text.strip())
        await update.message.reply_text(t(lang,"body_arm_prompt"), parse_mode="HTML")
        return BODY_ARM
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_LEG

async def body_add_arm(update, context):
    lang = get_lang(context)
    try:
        bm = context.user_data["bm"]
        bm["arm"] = _parse_decimal(update.message.text.strip())
        db.add_body_measurement(bm["cid"], bm["date"],
                                bm.get("weight"), bm.get("chest"), bm.get("waist"),
                                bm.get("hips"), bm.get("leg"), bm.get("arm"))
        try:
            d_obj = datetime.strptime(bm["date"], "%Y-%m-%d").date()
            d_fmt = fmt_date(d_obj, None, lang)
        except:
            d_fmt = bm["date"]
        await update.message.reply_text(
            t(lang,"body_saved", name=bm["name"], date=d_fmt),
            reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(t(lang,"invalid_decimal"), parse_mode="HTML")
        return BODY_ARM

# ── View measurements ─────────────────────────────────────────────
async def body_view_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML"); return
    await q.edit_message_text(t(lang,"body_select_client"),
                               reply_markup=client_list_keyboard(clients,"bodyview",lang), parse_mode="HTML")

async def body_view_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    entries = db.get_body_measurements(cid)
    if not entries:
        await q.edit_message_text(t(lang,"body_none"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML"); return
    txt = f"<b>📏 {c['name']}</b>\n" + "─"*28 + "\n\n"
    for e in entries:
        txt += _fmt_body_entry(e, lang) + "\n\n"
    if len(txt) > 4000:
        txt = txt[:3990] + "\n<i>…</i>"
    await q.edit_message_text(txt, reply_markup=body_menu_keyboard(lang), parse_mode="HTML")

# ── Edit measurement ──────────────────────────────────────────────
async def body_edit_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(t(lang,"body_select_client"),
                               reply_markup=client_list_keyboard(clients,"bodyeditcl",lang), parse_mode="HTML")
    return BODY_EDIT_SELECT_CLIENT

async def body_edit_select_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["bm_edit_cid"] = cid; context.user_data["bm_edit_name"] = c["name"]
    entries = db.get_body_measurements(cid)
    if not entries:
        await q.edit_message_text(t(lang,"body_none"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    kb = []
    for e in entries:
        try:
            d_obj = datetime.strptime(e["meas_date"], "%Y-%m-%d").date()
            label = fmt_date(d_obj, None, lang)
        except:
            label = e["meas_date"]
        kb.append([InlineKeyboardButton(label, callback_data=f"bodyeditentry:{e['id']}")])
    kb.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="body_menu")])
    await q.edit_message_text(t(lang,"body_select_entry",action="edit"),
                               reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return BODY_EDIT_SELECT_ENTRY

async def body_edit_select_entry(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    mid = int(q.data.split(":")[1])
    context.user_data["bm_edit_mid"] = mid
    e = db.get_body_measurement(mid)
    # store current values
    context.user_data["bm_edit_vals"] = {
        "date": e["meas_date"], "weight": e["weight"], "chest": e["chest"],
        "waist": e["waist"], "hips": e["hips"], "leg": e["leg"], "arm": e["arm"]
    }
    fields_en = ["date","weight","chest","waist","hips","leg","arm"]
    labels = {
        "date":   "📅 " + ("Date" if lang=="EN" else "Dată"),
        "weight": t(lang,"lbl_weight"), "chest": t(lang,"lbl_chest"),
        "waist":  t(lang,"lbl_waist"),  "hips":  t(lang,"lbl_hips"),
        "leg":    t(lang,"lbl_leg"),    "arm":   t(lang,"lbl_arm"),
    }
    kb = [[InlineKeyboardButton(labels[f], callback_data=f"bodyeditfield:{f}")] for f in fields_en]
    kb.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="body_menu")])
    await q.edit_message_text(
        t(lang,"body_edit_field_prompt") + "\n\n" + _fmt_body_entry(e, lang),
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return BODY_EDIT_FIELD

async def body_edit_field(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    field = q.data.split(":")[1]; context.user_data["bm_edit_field"] = field
    prompts = {
        "date":   t(lang,"body_date_prompt"),   "weight": t(lang,"body_weight_prompt"),
        "chest":  t(lang,"body_chest_prompt"),  "waist":  t(lang,"body_waist_prompt"),
        "hips":   t(lang,"body_hips_prompt"),   "leg":    t(lang,"body_leg_prompt"),
        "arm":    t(lang,"body_arm_prompt"),
    }
    await q.edit_message_text(prompts[field], parse_mode="HTML")
    return BODY_EDIT_VALUE

async def body_edit_value(update, context):
    lang = get_lang(context)
    field = context.user_data["bm_edit_field"]
    mid   = context.user_data["bm_edit_mid"]
    vals  = context.user_data["bm_edit_vals"]
    txt   = update.message.text.strip()
    try:
        if field == "date":
            d = datetime.strptime(txt, "%d/%m/%Y").date()
            vals["date"] = d.isoformat()
        else:
            vals[field] = _parse_decimal(txt)
        db.update_body_measurement(mid, vals["date"], vals["weight"], vals["chest"],
                                   vals["waist"], vals["hips"], vals["leg"], vals["arm"])
        await update.message.reply_text(t(lang,"body_updated"),
                                         reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    except ValueError:
        err = t(lang,"invalid_date") if field=="date" else t(lang,"invalid_decimal")
        await update.message.reply_text(err, parse_mode="HTML")
        return BODY_EDIT_VALUE

# ── Delete measurement ────────────────────────────────────────────
async def body_del_start(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    clients = db.get_all_clients()
    if not clients:
        await q.edit_message_text(t(lang,"no_clients"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    await q.edit_message_text(t(lang,"body_select_client"),
                               reply_markup=client_list_keyboard(clients,"bodydelcl",lang), parse_mode="HTML")
    return BODY_DEL_SELECT_CLIENT

async def body_del_select_client(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    cid = int(q.data.split(":")[1]); c = db.get_client(cid)
    context.user_data["bm_del_cid"] = cid; context.user_data["bm_del_name"] = c["name"]
    entries = db.get_body_measurements(cid)
    if not entries:
        await q.edit_message_text(t(lang,"body_none"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END
    kb = []
    for e in entries:
        try:
            d_obj = datetime.strptime(e["meas_date"], "%Y-%m-%d").date()
            label = fmt_date(d_obj, None, lang)
        except:
            label = e["meas_date"]
        kb.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"bodydelentry:{e['id']}")])
    kb.append([InlineKeyboardButton(t(lang,"btn_cancel"), callback_data="body_menu")])
    await q.edit_message_text(t(lang,"body_select_entry",action="delete"),
                               reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return BODY_DEL_SELECT_ENTRY

async def body_del_select_entry(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    mid = int(q.data.split(":")[1])
    context.user_data["bm_del_mid"] = mid
    e = db.get_body_measurement(mid)
    name = context.user_data["bm_del_name"]
    try:
        d_obj = datetime.strptime(e["meas_date"], "%Y-%m-%d").date()
        d_fmt = fmt_date(d_obj, None, lang)
    except:
        d_fmt = e["meas_date"]
    await q.edit_message_text(
        t(lang,"body_confirm_delete", date=d_fmt, name=name),
        reply_markup=confirm_keyboard(lang,"body_del_confirm","body_menu"), parse_mode="HTML")
    return BODY_DEL_CONFIRM

async def body_del_confirm(update, context):
    q = update.callback_query; await q.answer(); lang = get_lang(context)
    if q.data == "body_del_confirm":
        db.delete_body_measurement(context.user_data["bm_del_mid"])
        await q.edit_message_text(t(lang,"body_deleted"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
    else:
        await q.edit_message_text(t(lang,"deletion_cancelled"), reply_markup=body_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

async def cancel(update, context):
    lang = get_lang(context)
    await update.message.reply_text(t(lang,"cancelled"), reply_markup=main_menu_keyboard(lang), parse_mode="HTML")
    return ConversationHandler.END

async def unknown_callback(update, context):
    await update.callback_query.answer("—", show_alert=False)


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    async def cancel_to_clients(update, context):
        q = update.callback_query; await q.answer()
        lang = get_lang(context)
        await q.edit_message_text(
            t(lang,"clients_menu", count=len(db.get_all_clients()), max=MAX_CLIENTS),
            reply_markup=clients_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END

    async def cancel_to_pkg(update, context):
        q = update.callback_query; await q.answer()
        lang = get_lang(context)
        await q.edit_message_text(t(lang,"pkg_menu"), reply_markup=pkg_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END

    async def cancel_to_main(update, context):
        q = update.callback_query; await q.answer()
        lang = get_lang(context)
        await q.edit_message_text(t(lang,"main_menu"), reply_markup=main_menu_keyboard(lang), parse_mode="HTML")
        return ConversationHandler.END

    add_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_client_start, pattern="^add_client$")],
        states={
            ADD_CLIENT_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_name)],
            ADD_CLIENT_PHONE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_phone)],
            ADD_CLIENT_NOTES:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_notes)],
            ADD_CLIENT_PKG_MONTH:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_pkg_month)],
            ADD_CLIENT_PKG_BOUGHT:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_pkg_bought)],
            ADD_CLIENT_PKG_USED:[MessageHandler(filters.TEXT&~filters.COMMAND,add_client_pkg_used)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_clients, pattern="^clients_menu$"),
            CallbackQueryHandler(cancel_to_main, pattern="^main_menu$"),
        ])

    edit_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_client_start, pattern="^edit_client_start$")],
        states={
            EDIT_CLIENT_SELECT:[CallbackQueryHandler(edit_client_select,pattern="^editcl:")],
            EDIT_CLIENT_FIELD:[CallbackQueryHandler(edit_client_field,pattern="^editcl_field:")],
            EDIT_CLIENT_VALUE:[MessageHandler(filters.TEXT&~filters.COMMAND,edit_client_value)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_clients, pattern="^clients_menu$"),
            CallbackQueryHandler(cancel_to_main, pattern="^main_menu$"),
        ])

    del_client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_client_start, pattern="^delete_client$")],
        states={CONFIRM_DELETE_CLIENT:[
            CallbackQueryHandler(confirm_delete_client,pattern="^del_client:"),
            CallbackQueryHandler(execute_delete_client,pattern="^(confirm|cancel)_del_client$"),
        ]}, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_clients, pattern="^clients_menu$"),
            CallbackQueryHandler(cancel_to_main, pattern="^main_menu$"),
        ])

    add_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_session_start, pattern="^add_session$")],
        states={
            ADD_SESSION_CLIENT:[CallbackQueryHandler(add_session_client,pattern="^sess_client:")],
            ADD_SESSION_DATE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_date)],
            ADD_SESSION_TIME:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_time)],
            ADD_SESSION_DURATION:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_duration)],
            ADD_SESSION_NOTES:[MessageHandler(filters.TEXT&~filters.COMMAND,add_session_notes)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_main, pattern="^(main_menu|schedule_menu)$"),
        ])

    edit_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_session_start, pattern="^edit_session_start$")],
        states={
            EDIT_SESSION_SELECT:[CallbackQueryHandler(edit_session_select,pattern="^editsess:")],
            EDIT_SESSION_FIELD:[CallbackQueryHandler(edit_session_field,pattern="^editsess_field:")],
            EDIT_SESSION_VALUE:[MessageHandler(filters.TEXT&~filters.COMMAND,edit_session_value)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_main, pattern="^(main_menu|schedule_menu)$"),
        ])

    del_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_session_start, pattern="^delete_session$")],
        states={CONFIRM_DELETE_SESSION:[
            CallbackQueryHandler(confirm_delete_session,pattern="^del_sess:"),
            CallbackQueryHandler(execute_delete_session,pattern="^(confirm|cancel)_del_sess$"),
        ]}, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_main, pattern="^(main_menu|schedule_menu)$"),
        ])

    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_plan_start, pattern="^add_plan$")],
        states={
            ADD_PLAN_CLIENT:[CallbackQueryHandler(add_plan_client,pattern="^plan_client:")],
            ADD_PLAN_TITLE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_plan_title)],
            ADD_PLAN_CONTENT:[MessageHandler(filters.TEXT&~filters.COMMAND,add_plan_content)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_main, pattern="^(main_menu|workout_menu)$"),
        ])

    body_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(body_add_start, pattern="^body_add_start$")],
        states={
            BODY_SELECT_CLIENT:[CallbackQueryHandler(body_add_client, pattern="^bodyadd:")],
            BODY_DATE:  [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_date)],
            BODY_WEIGHT:[MessageHandler(filters.TEXT&~filters.COMMAND, body_add_weight)],
            BODY_CHEST: [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_chest)],
            BODY_WAIST: [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_waist)],
            BODY_HIPS:  [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_hips)],
            BODY_LEG:   [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_leg)],
            BODY_ARM:   [MessageHandler(filters.TEXT&~filters.COMMAND, body_add_arm)],
        }, fallbacks=[CommandHandler("cancel",cancel),
                      CallbackQueryHandler(lambda u,c: (u.callback_query.answer(), ConversationHandler.END)[1], pattern="^body_menu$")])

    body_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(body_edit_start, pattern="^body_edit_start$")],
        states={
            BODY_EDIT_SELECT_CLIENT:[CallbackQueryHandler(body_edit_select_client, pattern="^bodyeditcl:")],
            BODY_EDIT_SELECT_ENTRY: [CallbackQueryHandler(body_edit_select_entry,  pattern="^bodyeditentry:")],
            BODY_EDIT_FIELD:        [CallbackQueryHandler(body_edit_field,          pattern="^bodyeditfield:")],
            BODY_EDIT_VALUE:        [MessageHandler(filters.TEXT&~filters.COMMAND,  body_edit_value)],
        }, fallbacks=[CommandHandler("cancel",cancel),
                      CallbackQueryHandler(lambda u,c: (u.callback_query.answer(), ConversationHandler.END)[1], pattern="^body_menu$")])

    body_del_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(body_del_start, pattern="^body_del_start$")],
        states={
            BODY_DEL_SELECT_CLIENT:[CallbackQueryHandler(body_del_select_client, pattern="^bodydelcl:")],
            BODY_DEL_SELECT_ENTRY: [CallbackQueryHandler(body_del_select_entry,  pattern="^bodydelentry:")],
            BODY_DEL_CONFIRM:      [CallbackQueryHandler(body_del_confirm,        pattern="^(body_del_confirm|body_menu)$")],
        }, fallbacks=[CommandHandler("cancel",cancel),
                      CallbackQueryHandler(lambda u,c: (u.callback_query.answer(), ConversationHandler.END)[1], pattern="^body_menu$")])

    add_pkg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_pkg_start, pattern="^add_pkg_start$")],
        states={
            PKG_SELECT_CLIENT:[CallbackQueryHandler(pkg_select_client,pattern="^pkgcl:")],
            PKG_ENTER_MONTH:[MessageHandler(filters.TEXT&~filters.COMMAND,pkg_enter_month)],
            PKG_ENTER_BOUGHT:[MessageHandler(filters.TEXT&~filters.COMMAND,pkg_enter_bought)],
            PKG_ENTER_USED:[MessageHandler(filters.TEXT&~filters.COMMAND,pkg_enter_used)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_pkg, pattern="^pkg_menu$"),
            CallbackQueryHandler(cancel_to_main, pattern="^main_menu$"),
        ])

    edit_pkg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_pkg_used_start, pattern="^edit_pkg_used_start$")],
        states={
            PKG_EDIT_SELECT_CLIENT:[CallbackQueryHandler(edit_pkg_select_client,pattern="^editpkg:")],
            PKG_EDIT_SELECT_MONTH:[CallbackQueryHandler(edit_pkg_select_month,pattern="^editpkgm:")],
            PKG_EDIT_ENTER_USED:[MessageHandler(filters.TEXT&~filters.COMMAND,edit_pkg_enter_used)],
        }, fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_to_pkg, pattern="^pkg_menu$"),
            CallbackQueryHandler(cancel_to_main, pattern="^main_menu$"),
        ])

    app.add_handler(CommandHandler("start", start))
    for conv in [add_client_conv, edit_client_conv, del_client_conv,
                 add_session_conv, edit_session_conv, del_session_conv,
                 add_plan_conv, add_pkg_conv, edit_pkg_conv,
                 body_add_conv, body_edit_conv, body_del_conv]:
        app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(set_language,          pattern="^set_lang:"))
    app.add_handler(CallbackQueryHandler(change_lang,           pattern="^change_lang$"))
    app.add_handler(CallbackQueryHandler(cmd_main_menu,         pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_clients_menu,      pattern="^clients_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_clients,      pattern="^list_clients$"))
    app.add_handler(CallbackQueryHandler(cmd_client_history,    pattern="^client_history$"))
    app.add_handler(CallbackQueryHandler(delete_history_entry,  pattern="^del_hist:"))
    app.add_handler(CallbackQueryHandler(cmd_pkg_menu,          pattern="^pkg_menu$"))
    app.add_handler(CallbackQueryHandler(view_pkg_start,        pattern="^view_pkg_start$"))
    app.add_handler(CallbackQueryHandler(view_pkg_client,       pattern="^viewpkg:"))
    app.add_handler(CallbackQueryHandler(cmd_schedule_menu,     pattern="^schedule_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_view_today,        pattern="^view_today$"))
    app.add_handler(CallbackQueryHandler(cmd_view_weekly,       pattern="^view_weekly$"))
    app.add_handler(CallbackQueryHandler(cmd_view_monthly,      pattern="^view_monthly$"))
    app.add_handler(CallbackQueryHandler(cmd_view_all_sessions, pattern="^view_all_sessions$"))
    app.add_handler(CallbackQueryHandler(cmd_workout_menu,      pattern="^workout_menu$"))
    app.add_handler(CallbackQueryHandler(cmd_list_plans,        pattern="^list_plans$"))
    app.add_handler(CallbackQueryHandler(cmd_view_client_plan,  pattern="^view_client_plan$"))
    app.add_handler(CallbackQueryHandler(cmd_show_client_plans, pattern="^view_plan:"))
    app.add_handler(CallbackQueryHandler(cmd_body_menu,         pattern="^body_menu$"))
    app.add_handler(CallbackQueryHandler(body_view_start,       pattern="^body_view_start$"))
    app.add_handler(CallbackQueryHandler(body_view_client,      pattern="^bodyview:"))
    app.add_handler(CallbackQueryHandler(unknown_callback))

    setup_scheduler(app, db)
    logger.info("🏋️  FitCoach Bot v4 is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
