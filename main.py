import logging
import json
import os
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import Conflict, NetworkError
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

# ================= FLASK KEEP ALIVE =================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8647444509:AAH2aaMPSgZdhzU7U4WEJQEZfDN-h7_zXzE"
ADMIN_ID = 6589348050
GROUP_ID = -1003828486913

DATA_FILE = "data.json"

# ================= DATA =================
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "rates": {}, "match": "No Match", "bet_open": True}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

# ================= MENU =================
def menu():
    return ReplyKeyboardMarkup([
        ["💰 Balance", "📊 My Bets"],
        ["📊 Rates"],
        ["🎯 Bet"],
        ["💳 Payment", "🎁 Promotion"],
        ["💸 Withdrawal"]
    ], resize_keyboard=True)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "bets": []}
        save_data(data)

    await update.message.reply_text("👋 Welcome to CricPlay", reply_markup=menu())

# ================= BALANCE =================
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    bal = data["users"].get(uid, {}).get("balance", 0)
    await update.message.reply_text(f"💰 Balance: ₹{bal}")

# ================= RATES =================
async def rates_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["rates"]:
        await update.message.reply_text("No rates set")
        return

    msg = f"📊 {data['match']}\n\n"
    for t, r in data["rates"].items():
        msg += f"{t} → {r}x\n"

    await update.message.reply_text(msg)

# ================= SET RATE =================
async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    team = context.args[0].upper()
    rate = float(context.args[1])

    data["rates"][team] = rate
    save_data(data)

    msg = f"📢 Live Rate 🔥\n\n{team} → {rate}x"

    await update.message.reply_text(msg)
    await context.bot.send_message(GROUP_ID, msg)

# ================= SET MATCH =================
async def setmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data["match"] = " ".join(context.args)
    data["bet_open"] = True
    save_data(data)

    await update.message.reply_text(f"Match set: {data['match']}")

# ================= BET =================
async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    if not data["bet_open"]:
        await update.message.reply_text("Bet closed")
        return

    amount = int(context.args[0])
    team = context.args[1].upper()

    if data["users"][uid]["balance"] < amount:
        await update.message.reply_text("No balance")
        return

    win = int(amount * data["rates"][team])

    keyboard = [[InlineKeyboardButton("Confirm", callback_data=f"{amount}|{team}")]]
    await update.message.reply_text(
        f"Bet ₹{amount} on {team}\nWin ₹{win}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CONFIRM =================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    amount, team = q.data.split("|")
    amount = int(amount)

    data["users"][uid]["balance"] -= amount

    data["users"][uid]["bets"].append({
        "team": team,
        "amount": amount
    })

    save_data(data)

    await q.edit_message_text("Bet placed")

# ================= WITHDRAW REQUEST =================
async def withdraw_req(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text("Send amount and UPI details")

# ================= HANDLE =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if "balance" in text:
        await balance(update, context)

    elif "rates" in text:
        await rates_cmd(update, context)

    elif "payment" in text:
        await update.message.reply_text("Send payment screenshot")

    elif "withdrawal" in text:
        await withdraw_req(update, context)

    else:
        await update.message.reply_text("Use menu")

# ================= ERROR =================
async def error_handler(update, context):
    logger.error(context.error)

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bet", bet))
app.add_handler(CommandHandler("setrate", set_rate))
app.add_handler(CommandHandler("setmatch", setmatch))

app.add_handler(CallbackQueryHandler(confirm))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.add_error_handler(error_handler)

keep_alive()

print("Bot running...")
app.run_polling()
