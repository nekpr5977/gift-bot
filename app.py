import json
import os
import time
import threading
from flask import Flask, jsonify
from telebot import TeleBot, types
from telebot.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN = int(os.getenv("ADMIN_ID", 0))
# ===============================

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь переменную в Render.")

bot = TeleBot(TOKEN)
app = Flask(__name__)

DATA_FILE = "data.json"
AUTO_BUY_ENABLED = True
MAX_PRICE_STARS = 10
MAX_PRICE_RUB = 50
MARKUP_PERCENT = 30
CHECK_INTERVAL = 60

# ========== ЗАГРУЗКА ДАННЫХ ==========
def load_data():
    if not os.path.exists(DATA_FILE):
        default = {
            "gifts": [],
            "users": {},
            "auto_buy_log": [],
            "stats": {"total_bought": 0, "total_sold": 0, "total_spent": 0, "total_earned": 0}
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ========== АВТО-СКУПЩИК ==========
def fetch_market_nfts():
    return [
        {"id": 101, "name": "Дракон", "price_stars": 5, "price_rub": 25},
        {"id": 102, "name": "Меч", "price_stars": 8, "price_rub": 40},
        {"id": 103, "name": "Щит", "price_stars": 12, "price_rub": 60},
        {"id": 104, "name": "Корона", "price_stars": 3, "price_rub": 15},
        {"id": 105, "name": "Кольцо", "price_stars": 7, "price_rub": 35},
    ]

def auto_buy_worker():
    while True:
        if not AUTO_BUY_ENABLED:
            time.sleep(CHECK_INTERVAL)
            continue
        try:
            data = load_data()
            market_nfts = fetch_market_nfts()
            for nft in market_nfts:
                if any(g.get("market_id") == nft["id"] for g in data["gifts"]):
                    continue
                if nft["price_stars"] <= MAX_PRICE_STARS or nft["price_rub"] <= MAX_PRICE_RUB:
                    new_price_stars = int(nft["price_stars"] * (1 + MARKUP_PERCENT / 100))
                    new_price_rub = int(nft["price_rub"] * (1 + MARKUP_PERCENT / 100))
                    new_id = max([g["id"] for g in data["gifts"]] + [0]) + 1
                    data["gifts"].append({
                        "id": new_id,
                        "name": f"{nft['name']} (авто)",
                        "description": f"Куплен авто. Был {nft['price_stars']}⭐ / {nft['price_rub']}₽",
                        "price_stars": new_price_stars,
                        "price_rub": new_price_rub,
                        "image": "https://via.placeholder.com/200/00ff88",
                        "market_id": nft["id"],
                        "bought_at": datetime.now().isoformat()
                    })
                    data["auto_buy_log"].append({
                        "name": nft["name"],
                        "bought_price_stars": nft["price_stars"],
                        "bought_price_rub": nft["price_rub"],
                        "sold_price_stars": new_price_stars,
                        "sold_price_rub": new_price_rub,
                        "timestamp": datetime.now().isoformat()
                    })
                    data["stats"]["total_bought"] += 1
                    data["stats"]["total_spent"] += nft["price_rub"]
                    save_data(data)
                    print(f"✅ Куплен: {nft['name']} → продаём за {new_price_stars}⭐ / {new_price_rub}₽")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(CHECK_INTERVAL)

threading.Thread(target=auto_buy_worker, daemon=True).start()

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_stats = types.InlineKeyboardButton("📊 Статистика", callback_data="stats")
    markup.add(btn_stats)
    bot.send_message(
        message.chat.id,
        "🎁 *NFT Gift Store с авто-скупом!*\n\n"
        "Команды:\n"
        "/add_gift - добавить товар (только админ)\n"
        "/buy [ID] - купить товар\n"
        "/list - список товаров",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def show_stats(call):
    data = load_data()
    s = data["stats"]
    text = (
        f"📊 *Статистика*\n"
        f"🛒 Куплено авто: {s['total_bought']}\n"
        f"💰 Продано: {s['total_sold']}\n"
        f"💸 Потрачено: {s['total_spent']}₽\n"
        f"💵 Заработано: {s['total_earned']}₽"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['add_gift'])
def add_gift(message):
    if message.from_user.id != ADMIN:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    try:
        parts = message.text.split(maxsplit=1)[1].split("|")
        name, desc, ps, pr = parts[0].strip(), parts[1].strip(), int(parts[2].strip()), int(parts[3].strip())
        data = load_data()
        new_id = max([g["id"] for g in data["gifts"]] + [0]) + 1
        data["gifts"].append({
            "id": new_id,
            "name": name,
            "description": desc,
            "price_stars": ps,
            "price_rub": pr,
            "image": "https://via.placeholder.com/200",
            "manual": True
        })
        save_data(data)
        bot.reply_to(message, f"✅ *{name}* добавлен!\n⭐ {ps} Stars\n💳 {pr} ₽", parse_mode="Markdown")
    except:
        bot.reply_to(
            message,
            "❌ Формат: `/add_gift Название | Описание | Цена_Stars | Цена_рубли`\n"
            "Пример: `/add_gift Алмаз | Редкий | 50 | 250`",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['buy'])
def buy_gift(message):
    try:
        gift_id = int(message.text.split()[1])
        data = load_data()
        gift = next((g for g in data["gifts"] if g["id"] == gift_id), None)
        if not gift:
            bot.reply_to(message, "❌ Подарок не найден")
            return
        prices = [LabeledPrice(label=gift['name'], amount=gift['price_stars'])]
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Покупка: {gift['name']}",
            description=gift['description'],
            payload=f"gift_{gift_id}_{message.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="gift_purchase"
        )
    except:
        bot.reply_to(message, "❌ Используй: `/buy [ID товара]`\nПосмотри ID через /list", parse_mode="Markdown")

@bot.message_handler(commands=['list'])
def list_gifts(message):
    data = load_data()
    if not data["gifts"]:
        bot.reply_to(message, "📭 Пока нет товаров")
        return
    text = "📦 *Доступные подарки:*\n\n"
    for g in data["gifts"]:
        text += f"ID: `{g['id']}` | {g['name']} | ⭐ {g['price_stars']} | 💳 {g['price_rub']}₽\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.pre_checkout_query_handler(func=lambda q: True)
def handle_pre_checkout(query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payload = message.successful_payment.invoice_payload
    _, gift_id, user_id = payload.split("_")
    data = load_data()
    gift = next((g for g in data["gifts"] if g["id"] == int(gift_id)), None)
    if not gift:
        bot.send_message(message.chat.id, "❌ Ошибка")
        return
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"purchases": []}
    data["users"][str(user_id)]["purchases"].append(gift["name"])
    data["stats"]["total_sold"] += 1
    data["stats"]["total_earned"] += gift["price_rub"]
    save_data(data)
    bot.send_message(message.chat.id, f"🎉 Ты купил {gift['name']}!")

# ========== FLASK (чтобы Render не падал) ==========
@app.route('/')
def home():
    return jsonify({"status": "Bot is running!", "version": "1.0"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("🤖 Бот запущен!")
    # Запускаем бота в отдельном потоке, чтобы Flask не блокировал polling
    def run_bot():
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    threading.Thread(target=run_bot, daemon=True).start()
    # Запускаем Flask
    app.run(host="0.0.0.0", port=port)
