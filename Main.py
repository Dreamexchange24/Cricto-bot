import logging
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import Conflict, NetworkError
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8647444509:AAH2aaMPSgZdhzU7U4WEJQEZfDN-h7_zXzE"
ADMIN_ID = 6589348050
GROUP_ID = -1003828486913

users = {}

rates = {}

current_match = "No Match Set"
bet_open = True

payment_text = "💳 Send payment & screenshot"
payment_photo = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users:
        users[uid] = {"balance": 0, "bets": []}

    keyboard = [
        ["💰 Balance", "📊 My Bets"],
        ["📊 Rates"],
        ["🎯 Bet"],
        ["💳 Payment", "🎁 Promotion"],
        ["💸 Withdrawal"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Welcome to Cricto Bot\n\nSelect option below 👇",
        reply_markup=reply_markup
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = users.get(user_id, {}).get("balance", 0)
    await update.message.reply_text(f"💰 Balance: ₹{bal}")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /deposit <user_id> <amount>")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        if user_id not in users:
            users[user_id] = {"balance": 0}

        users[user_id]["balance"] += amount

        await context.bot.send_message(chat_id=user_id, text=f"✅ ₹{amount} added")
        await update.message.reply_text("Deposit done")
    except ValueError:
        await update.message.reply_text("❌ Please provide valid user_id and amount.")

async def broadcast_all(context, message):
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
        except Exception:
            pass

async def rates_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not rates:
        await update.message.reply_text("No rates set yet")
        return
    msg = f"📊 {current_match} Rates 🔥\n\n"
    for team, rate in rates.items():
        msg += f"{team} → {rate}x\n"
    await update.message.reply_text(msg)

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Use: /setrate TEAM RATE")
        return

    try:
        team = context.args[0].upper()
        rate = float(context.args[1])

        rates[team] = rate

        msg = (
            f"📢 Live Rate Update 🔥\n\n"
            f"🏏 {current_match}\n\n"
            f"🔵 {team} → {rate}x\n\n"
            f"💬 Place your bets now!"
        )

        await update.message.reply_text(msg)

        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=msg)
        except Exception:
            pass

        await broadcast_all(context, msg)
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid rate.")

async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global payment_text, payment_photo

    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        payment_text = " ".join(context.args)

    if update.message.reply_to_message and update.message.reply_to_message.photo:
        payment_photo = update.message.reply_to_message.photo[-1].file_id

    await update.message.reply_text("✅ Payment details updated")

async def setmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_match

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /setmatch <match name>")
        return

    global bet_open
    current_match = " ".join(context.args)
    bet_open = True
    await update.message.reply_text(f"✅ Match Updated: {current_match}\n✅ Betting is now OPEN")

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not bet_open:
        await update.message.reply_text("❌ Betting is closed")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Use: /bet <amount> <team>")
        return

    try:
        amount = int(context.args[0])
        team = context.args[1].upper()

        if team not in rates:
            await update.message.reply_text("Invalid team")
            return

        if uid not in users or users[uid]["balance"] < amount:
            await update.message.reply_text("Not enough balance")
            return

        win = int(amount * rates[team])

        keyboard = [[InlineKeyboardButton("✅ Confirm Bet", callback_data=f"confirm_{amount}_{team}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎯 Bet Preview:\n\n₹{amount} on {team}\n💰 Winning: ₹{win}\n\nConfirm?",
            reply_markup=reply_markup
        )
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid amount.")

async def confirm_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data.split("_")
    amount = int(data[1])
    team = data[2]

    if uid not in users or users[uid]["balance"] < amount:
        await query.edit_message_text("❌ Not enough balance")
        return

    if team not in rates:
        await query.edit_message_text("❌ Invalid team")
        return

    win = int(amount * rates[team])

    users[uid]["balance"] -= amount

    if "bets" not in users[uid]:
        users[uid]["bets"] = []

    users[uid]["bets"].append({
        "match": current_match,
        "team": team,
        "amount": amount,
        "win": win
    })

    await query.edit_message_text(
        f"✅ Bet Placed!\n\nMatch: {current_match}\n₹{amount} on {team}\n💰 Win ₹{win}"
    )

async def mybets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in users or "bets" not in users[user_id] or not users[user_id]["bets"]:
        await update.message.reply_text("No bets placed")
        return

    msg = "📊 Your Bets:\n\n"
    total = 0

    for b in users[user_id]["bets"]:
        msg += f"{b['team']} → ₹{b['amount']} (Win: ₹{b['win']})\n"
        total += b["win"]

    msg += f"\n💰 Total Winning: ₹{total}"
    await update.message.reply_text(msg)

async def hedge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Use: /hedge <amount> <team1> <team2>")
        return

    try:
        amount = float(context.args[0])
        team1 = context.args[1].upper()
        team2 = context.args[2].upper()

        if team1 not in rates or team2 not in rates:
            await update.message.reply_text("Invalid team")
            return

        rate1 = rates[team1]
        rate2 = rates[team2]
        hedge_amount = (amount * rate1) / rate2

        await update.message.reply_text(
            f"🔁 Hedge Calculation:\n\n"
            f"{team1} bet: ₹{int(amount)}\n"
            f"{team2} bet: ₹{int(hedge_amount)}\n\n"
            f"👉 Use this to balance profit"
        )
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid amount.")

async def result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /result <team>")
        return

    global bet_open
    winner = context.args[0].upper()

    result_msg = (
        f"🏆 Match Result Declared!\n\n"
        f"🏏 {current_match}\n\n"
        f"✅ Winner: {winner}\n\n"
        f"💰 Winnings updated in your account\n\n"
        f"👉 Check your balance now"
    )

    for user_id in users:
        if "bets" not in users[user_id]:
            continue

        remaining_bets = []
        total_win = 0

        for b in users[user_id]["bets"]:
            if b.get("match") == current_match:
                if b["team"] == winner:
                    total_win += b["win"]
            else:
                remaining_bets.append(b)

        users[user_id]["balance"] += total_win
        users[user_id]["bets"] = remaining_bets

        if total_win > 0:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{result_msg}\n\n🎉 You won ₹{total_win}!"
                )
            except Exception:
                pass
        else:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{result_msg}\n\n❌ Better luck next time!"
                )
            except Exception:
                pass

    rates.clear()
    bet_open = False

    await update.message.reply_text(
        f"✅ Result declared: {current_match} → {winner}\n\n"
        f"⚠️ Rates cleared. Use /setmatch to start new match."
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /withdraw <user_id> <amount>")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        if user_id not in users:
            await update.message.reply_text("User not found")
            return

        if users[user_id]["balance"] < amount:
            await update.message.reply_text("❌ Insufficient balance")
            return

        users[user_id]["balance"] -= amount

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"💸 Withdrawal ₹{amount} processed\n💰 Remaining Balance: ₹{users[user_id]['balance']}"
            )
        except Exception:
            pass

        await update.message.reply_text("✅ Withdrawal deducted")
    except ValueError:
        await update.message.reply_text("❌ Please provide valid user_id and amount.")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /bonus <user_id> <amount>")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        if user_id not in users:
            users[user_id] = {"balance": 0}

        users[user_id]["balance"] += amount

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎁 Bonus Added: ₹{amount}\n💰 Updated Balance!"
            )
        except Exception:
            pass

        await update.message.reply_text("✅ Bonus added successfully")
    except ValueError:
        await update.message.reply_text("❌ Please provide valid user_id and amount.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /check <user_id>")
        return

    try:
        user_id = int(context.args[0])
        if user_id not in users:
            await update.message.reply_text("User not found")
            return

        bal = users[user_id]["balance"]
        await update.message.reply_text(f"{user_id} → ₹{bal}")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user_id.")

async def allbets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = "📊 Active Bets:\n\n"
    team_totals = {}
    team_wins = {}

    for uid, data in users.items():
        if "bets" not in data or not data["bets"]:
            continue

        msg += f"👤 {uid}\n"

        for b in data["bets"]:
            msg += f"{b.get('match', '?')} | {b['team']} ₹{b['amount']} (Win ₹{b['win']})\n"
            team_totals[b["team"]] = team_totals.get(b["team"], 0) + b["amount"]
            team_wins[b["team"]] = team_wins.get(b["team"], 0) + b["win"]

        msg += "\n"

    if team_totals:
        msg += "\n📊 Team Summary:\n\n"
        for team in team_totals:
            msg += f"{team} → Bet ₹{team_totals[team]} | Win ₹{team_wins[team]}\n"
    else:
        msg = "No active bets"

    await update.message.reply_text(msg)

async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = "💰 All Users Balance:\n\n"
    total = 0

    for uid, data in users.items():
        bal = data.get("balance", 0)
        msg += f"👤 {uid} → ₹{bal}\n"
        total += bal

    msg += f"\n💰 Total Balance: ₹{total}"

    await update.message.reply_text(msg)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    text_lower = text.lower()

    if user.id not in users:
        users[user.id] = {"balance": 0, "bets": []}

    await context.bot.send_message(ADMIN_ID, f"{user.first_name} ({user.id}): {text}")

    if "balance" in text_lower:
        bal = users[user.id]["balance"]
        await update.message.reply_text(f"💰 Balance: ₹{bal}")

    elif "my bets" in text_lower:
        bets = users[user.id].get("bets", [])
        if not bets:
            await update.message.reply_text("No bets placed")
            return
        msg = "📊 Your Bets:\n\n"
        for b in bets:
            msg += f"{b.get('match', '?')} | {b['team']} ₹{b['amount']} (Win ₹{b['win']})\n"
        await update.message.reply_text(msg)

    elif "bet" in text_lower:
        await update.message.reply_text(
            "🎯 How to place bet:\n\n"
            "Type like this 👇\n"
            "/bet 500 CSK\n\n"
            "👉 You will see a preview first\n"
            "👉 Then confirm your bet"
        )

    elif "rates" in text_lower:
        if not rates:
            await update.message.reply_text("No rates set yet")
            return
        msg = f"📊 {current_match} Rates 🔥\n\n"
        for t, r in rates.items():
            msg += f"{t} → {r}x\n"
        await update.message.reply_text(msg)

    elif "payment" in text_lower:
        if payment_photo:
            await update.message.reply_photo(photo=payment_photo, caption=payment_text)
        else:
            await update.message.reply_photo(
                photo=open("attached_assets/IMG_6964_1774121473368.jpeg", "rb"),
                caption=payment_text
            )

    elif "promotion" in text_lower:
        await update.message.reply_text("🔥 Latest Offers Available!")

    elif "withdrawal" in text_lower:
        await update.message.reply_text("💸 Send details:\nName\nAccount\nIFSC\nUPI\nAmount")

    else:
        await update.message.reply_text("Use buttons below 👇")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photo = update.message.photo[-1].file_id

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"📸 Screenshot from {user.first_name} ({user.id})"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.error("Conflict: Another bot instance is running with this token. Stop the other instance first.")
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Network error: {context.error}")
    else:
        logger.error(f"Error: {context.error}")

async def post_init(application):
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook cleared. Bot is starting...")

app = (
    ApplicationBuilder()
    .token(TOKEN)
    .post_init(post_init)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("deposit", deposit))
app.add_handler(CommandHandler("setpayment", setpayment))
app.add_handler(CommandHandler("setmatch", setmatch))
app.add_handler(CommandHandler("bet", bet))
app.add_handler(CommandHandler("mybets", mybets))
app.add_handler(CommandHandler("hedge", hedge))
app.add_handler(CommandHandler("rates", rates_cmd))
app.add_handler(CommandHandler("setrate", set_rate))
app.add_handler(CommandHandler("result", result))
app.add_handler(CommandHandler("withdraw", withdraw))
app.add_handler(CommandHandler("bonus", bonus))
app.add_handler(CommandHandler("check", check))
app.add_handler(CommandHandler("allbets", allbets))
app.add_handler(CommandHandler("allusers", allusers))
app.add_handler(CallbackQueryHandler(confirm_bet, pattern="^confirm_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_error_handler(error_handler)

keep_alive()
logger.info("Starting bot...")
app.run_polling()
