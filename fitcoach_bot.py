#!/usr/bin/env python3
"""
FitCoach Bot — Telegram Bot for Fitness Trainers
Built with python-telegram-bot v20+ (async)

Requirements:
    pip install python-telegram-bot==20.7

Usage:
    1. Create a bot via @BotFather on Telegram
    2. Copy your bot token below
    3. Run: python fitcoach_bot.py
"""

import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ─────────────────────────────────────────────
# Configuration — replace with your bot token
# ─────────────────────────────────────────────
BOT_TOKEN = "trytobefit_bot"
DATA_FILE  = "clients.json"

# ─────────────────────────────────────────────
# Data helpers — load/save client data to JSON
# ─────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
# /start — Welcome message for the trainer
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💪 *Welcome to FitCoach Bot!*\n\n"
        "Your personal training assistant. Here's what I can do:\n\n"
        "/addclient [name] [time] — Add a new client\n"
        "/listclients — View all clients & schedules\n"
        "/schedule [client] [day] [time] — Update session time\n"
        "/workout [client] [plan] — Assign a workout plan\n"
        "/today — Show today's sessions\n"
        "/remove [client] — Remove a client\n\n"
        "Let's get to work! 🏋️",
        parse_mode="Markdown",
    )

# ─────────────────────────────────────────────
# /addclient [name] [time] — Add a new client
# Example: /addclient John 09:00
# ─────────────────────────────────────────────
async def add_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addclient [name] [time]\nExample: /addclient John 09:00"
        )
        return

    name = context.args[0].capitalize()
    time = context.args[1]
    data = load_data()

    if name in data:
        await update.message.reply_text(f"⚠️ Client '{name}' already exists.")
        return

    data[name] = {"time": time, "schedule": {}, "workout": "Not assigned"}
    save_data(data)
    await update.message.reply_text(
        f"✅ Client *{name}* added — session time: *{time}*", parse_mode="Markdown"
    )

# ─────────────────────────────────────────────
# /listclients — List all clients and their times
# ─────────────────────────────────────────────
async def list_clients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data:
        await update.message.reply_text("No clients yet. Use /addclient to get started.")
        return

    lines = ["📋 *Your Clients:*\n"]
    for i, (name, info) in enumerate(data.items(), 1):
        lines.append(
            f"{i}. *{name}*\n"
            f"   ⏰ Time: {info['time']}\n"
            f"   🏋️ Workout: {info['workout']}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─────────────────────────────────────────────
# /schedule [client] [day] [time] — Update session
# Example: /schedule John Monday 08:30
# ─────────────────────────────────────────────
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /schedule [client] [day] [time]\n"
            "Example: /schedule John Monday 08:30"
        )
        return

    name = context.args[0].capitalize()
    day  = context.args[1].capitalize()
    time = context.args[2]
    data = load_data()

    if name not in data:
        await update.message.reply_text(f"❌ Client '{name}' not found.")
        return

    data[name]["schedule"][day] = time
    data[name]["time"] = time
    save_data(data)
    await update.message.reply_text(
        f"📅 Scheduled *{name}* on *{day}* at *{time}*", parse_mode="Markdown"
    )

# ─────────────────────────────────────────────
# /workout [client] [plan] — Assign workout plan
# Example: /workout John "Upper Body Strength"
# ─────────────────────────────────────────────
async def workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /workout [client] [plan]\n"
            "Example: /workout John Upper Body Strength"
        )
        return

    name = context.args[0].capitalize()
    plan = " ".join(context.args[1:])
    data = load_data()

    if name not in data:
        await update.message.reply_text(f"❌ Client '{name}' not found.")
        return

    data[name]["workout"] = plan
    save_data(data)
    await update.message.reply_text(
        f"🏋️ Assigned *{plan}* to *{name}*", parse_mode="Markdown"
    )

# ─────────────────────────────────────────────
# /today — Show all sessions for today
# ─────────────────────────────────────────────
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data  = load_data()
    today_name = datetime.now().strftime("%A")  # e.g. "Monday"

    sessions = [
        (name, info)
        for name, info in data.items()
        if today_name in info.get("schedule", {})
    ]

    if not sessions:
        await update.message.reply_text(
            f"📭 No sessions scheduled for *{today_name}*.", parse_mode="Markdown"
        )
        return

    lines = [f"📆 *Sessions for {today_name}:*\n"]
    for name, info in sorted(sessions, key=lambda x: x[1]["schedule"][today_name]):
        lines.append(
            f"• *{name}* — {info['schedule'][today_name]}\n"
            f"  Workout: {info['workout']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─────────────────────────────────────────────
# /remove [client] — Remove a client
# Example: /remove John
# ─────────────────────────────────────────────
async def remove_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /remove [client]\nExample: /remove John")
        return

    name = context.args[0].capitalize()
    data = load_data()

    if name not in data:
        await update.message.reply_text(f"❌ Client '{name}' not found.")
        return

    del data[name]
    save_data(data)
    await update.message.reply_text(f"🗑️ Client *{name}* removed.", parse_mode="Markdown")

# ─────────────────────────────────────────────
# Main — Initialize and run the bot
# ─────────────────────────────────────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("addclient",   add_client))
    app.add_handler(CommandHandler("listclients", list_clients))
    app.add_handler(CommandHandler("schedule",    schedule))
    app.add_handler(CommandHandler("workout",     workout))
    app.add_handler(CommandHandler("today",       today))
    app.add_handler(CommandHandler("remove",      remove_client))

    print("FitCoach Bot is running... Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
