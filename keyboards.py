"""
FitCoach Bot — Inline keyboard builders
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤  Clients", callback_data="clients_menu"),
            InlineKeyboardButton("📅  Schedule", callback_data="schedule_menu"),
        ],
        [
            InlineKeyboardButton("📋  Workout Plans", callback_data="workout_menu"),
        ],
    ])


def clients_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕  Add Client",    callback_data="add_client"),
            InlineKeyboardButton("🗑  Remove Client", callback_data="delete_client"),
        ],
        [
            InlineKeyboardButton("📋  View All Clients", callback_data="list_clients"),
        ],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])


def schedule_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅  Today",   callback_data="view_today"),
            InlineKeyboardButton("📆  This Week", callback_data="view_weekly"),
            InlineKeyboardButton("🗓  This Month", callback_data="view_monthly"),
        ],
        [
            InlineKeyboardButton("➕  Add Session",    callback_data="add_session"),
            InlineKeyboardButton("🗑  Cancel Session", callback_data="delete_session"),
        ],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])


def workout_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕  New Plan",     callback_data="add_plan"),
            InlineKeyboardButton("📋  View Plans",   callback_data="list_plans"),
        ],
        [
            InlineKeyboardButton("👤  Plans by Client", callback_data="view_client_plan"),
        ],
        [InlineKeyboardButton("↩  Main Menu", callback_data="main_menu")],
    ])


def back_keyboard(target: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩  Back", callback_data=target)]
    ])


def confirm_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅  Confirm", callback_data=confirm_data),
            InlineKeyboardButton("✖  Cancel",  callback_data=cancel_data),
        ]
    ])


def days_keyboard() -> InlineKeyboardMarkup:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(d, callback_data=f"day:{d}") for d in days]
    ])


def time_keyboard() -> InlineKeyboardMarkup:
    """Quick-select common training times."""
    times = [
        "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
        "18:00", "19:00", "20:00", "21:00",
    ]
    rows = []
    for i in range(0, len(times), 4):
        rows.append([
            InlineKeyboardButton(t, callback_data=f"time:{t}") for t in times[i:i+4]
        ])
    return InlineKeyboardMarkup(rows)


def client_list_keyboard(clients: list, prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for c in clients:
        rows.append([InlineKeyboardButton(
            c["name"], callback_data=f"{prefix}:{c['id']}"
        )])
    rows.append([InlineKeyboardButton("✖  Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)
