"""
FitCoach Bot — Message templates
Professional, organised, fitness-coach tone.
"""

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

# ── Clients ──────────────────────────────────────────────────────
CLIENTS_MENU_MSG = (
    "👤 <b>Client Management</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Active clients: <b>{count} / {max}</b>\n\n"
    "Add or remove clients, or view your full roster."
)

NO_CLIENTS_MSG = (
    "👤 <b>No clients yet.</b>\n\n"
    "Add your first client to get started."
)

MAX_CLIENTS_MSG = (
    "⚠️ <b>Client limit reached ({max} clients).</b>\n\n"
    "Remove an existing client before adding a new one."
)

ADD_CLIENT_NAME_MSG = (
    "➕ <b>New Client</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Enter the client's full name:"
)

ADD_CLIENT_PHONE_MSG = (
    "Enter the client's phone number:\n"
    "<i>(Type <code>skip</code> to leave blank)</i>"
)

ADD_CLIENT_NOTES_MSG = (
    "Any notes for this client?\n"
    "<i>e.g. injuries, goals, preferences\n"
    "(Type <code>skip</code> to leave blank)</i>"
)

CLIENT_ADDED_MSG = (
    "✅ <b>{name}</b> added to your roster.\n"
    "<i>Client ID: {id}</i>"
)

CONFIRM_DELETE_CLIENT_MSG = (
    "⚠️ <b>Remove Client</b>\n\n"
    "Remove <b>{name}</b> from your roster?\n\n"
    "<i>All sessions and workout plans for this client will also be deleted. "
    "This cannot be undone.</i>"
)

CLIENT_DELETED_MSG = "✅ <b>{name}</b> has been removed from your roster."

# ── Schedule ─────────────────────────────────────────────────────
SCHEDULE_MENU_MSG = (
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
    "👤 Client  : <b>{name}</b>\n"
    "📅 Date    : {date}\n"
    "🕐 Time    : {time}\n"
    "⏱ Duration : {duration} min\n\n"
    "<i>You'll receive a reminder 1 and 2 hours before this session.</i>"
)

CONFIRM_DELETE_SESSION_MSG = (
    "⚠️ <b>Cancel Session</b>\n\n"
    "Cancel the session with <b>{name}</b>\n"
    "on {date} at {time}?\n\n"
    "<i>This action cannot be undone.</i>"
)

# ── Reminders ────────────────────────────────────────────────────
REMINDER_MSG = (
    "🔔 <b>Session Reminder</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "⏰ <b>{hours} hour{plural}</b> until your session with:\n\n"
    "👤 <b>{name}</b>\n"
    "🕐 {time}  •  {duration} min"
)

# ── Workout plans ─────────────────────────────────────────────────
WORKOUT_MENU_MSG = (
    "📋 <b>Workout Plans</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Create and manage personalised workout plans for each client."
)

PLAN_ADDED_MSG = (
    "✅ <b>Workout Plan Saved</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "👤 Client : <b>{name}</b>\n"
    "📋 Plan    : {title}"
)
