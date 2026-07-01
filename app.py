import os
import json
import time
import threading
import requests
from flask import Flask, request, jsonify, send_from_directory
from telebot import TeleBot, types
from telebot.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Авто-скуп
AUTO_BUY_ENABLED = True
MAX_PRICE_STARS = 10
MAX_PRICE_RUB = 50
MARKUP_PERCENT = 30
CHECK_INTERVAL = 30

bot = TeleBot(TOKEN)
app = Flask(__name__)
DATA_FILE = "data.json"

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

# ========== МИНИ-ПРИЛОЖЕНИЕ (HTML) ==========
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>NFT Store</title>
    <script src="https://telegram-web-app.js.org/telegram-web-app.js"></script>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, sans-serif; background: #0a0a0f; color: #fff; padding: 16px; }
        .gift { background: #1a1a2e; border-radius: 16px; padding: 16px; margin-bottom: 12px; border: 1px solid #2a2a4e; }
        .gift h3 { font-size: 18px; margin-bottom: 4px; }
        .gift p { color: #888; font-size: 14px; }
        .gift .price { color: #f7971e; font-weight: 700; margin-top: 8px; }
        .btn-buy { background: #f7971e; color: #000; border: none; padding: 10px 20px; border-radius: 12px; font-weight: 700; cursor: pointer; margin-top: 8px; width: 100%; }
        .btn-buy:active { transform: scale(0.97); }
        .btn-buy:disabled { opacity: 0.5; }
        .loading { text-align: center; padding: 40px; color: #666; }
    </style>
</head>
<body>
    <div id="app">
        <h1 style="margin-bottom:16px;">🎁 NFT Store</h1>
        <div id="gifts">Загрузка...</div>
    </div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        async function loadGifts() {
            try {
                const resp = await fetch('/api/gifts');
                const data = await resp.json();
                const container = document.getElementById('gifts');
                if (data.gifts.length === 0) {
                    container.innerHTML = '<div style="text-align:center;color:#666;">Пока нет товаров</div>';
                    return;
                }
                container.innerHTML = data.gifts.map(g => `
                    <div class="gift">
                        <h3>${g.name}</h3>
                        <p>${g.description || ''}</p>
                        <div class="price">⭐ ${g.price_stars} / 💳 ${g.price_rub} руб.</div>
                        <button class="btn-buy" onclick="buyGift(${g.id})">Купить</button>
                    </div>
                `).join('');
            } catch(e) {
                document.getElementById('gifts').innerHTML = '<div style="color:#f44;">Ошибка загрузки</div>';
            }
        }

        function buyGift(giftId) {
            tg.sendData(JSON.stringify({ action: 'buy', gift_id: giftId }));
        }

        loadGifts();
    </script>
</body>
</html>
"""

# ========== МОНИТОРИНГ РЫНКА (ИМИТАЦИЯ) ==========
def fetch_market_nfts():
    # Здесь будет реальный API GetGems
    return [
        {"id": 101, "name": "Dragon", "price_stars": 5, "price_rub": 25},
        {"id": 102, "name": "Sword", "price_stars": 8, "price_rub": 40},
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
                        "description": f"Куплен за {nft['price_stars']}⭐",
                        "price_stars": new_price_stars,
                        "price_rub": new_price_rub,
                        "market_id": nft["id"],
                        "bought_at": datetime.now().isoformat()
                    })
                    data["auto_buy_log"].append({
                        "name": nft["name"],
                        "bought_price_stars": nft["price_stars"],
                        "sold_price_stars": new_price_stars,
                        "timestamp": datetime.now().isoformat()
                    })
                    data["stats"]["total_bought"] += 1
                    data["stats"]["total_spent"] += nft["price_rub"]
                    save_data(data)
                    print(f"Авто-скуп: {nft['name']} -> {new_price_stars}⭐")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Ошибка авто-скупа: {e}")
            time.sleep(CHECK_INTERVAL)

threading.Thread(target=auto_buy_worker, daemon=True).start()

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    web_app = types.WebAppInfo(f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost')}")
    btn = types.InlineKeyboardButton("🛍 Открыть магазин", web_app=web_app)
    markup.add(btn)
    bot.send_message(
        message.chat.id,
        "🎁 NFT Store\n\nНажми кнопку, чтобы открыть магазин.",
        reply_markup=markup
    )

# ========== API ДЛЯ MINI APP ==========
@app.route('/')
def index():
    return HTML_PAGE

@app.route('/api/gifts')
def api_gifts():
    data = load_data()
    return jsonify({"gifts": data["gifts"]})

@app.route('/api/buy', methods=['POST'])
def api_buy():
    try:
        req = request.get_json()
        gift_id = req.get('gift_id')
        user_id = req.get('user_id')
        data = load_data()
        gift = next((g for g in data["gifts"] if g["id"] == gift_id), None)
        if not gift:
            return jsonify({"error": "Not found"}), 404
        # Здесь будет реальная оплата
        return jsonify({"status": "ok", "message": f"Куплен {gift['name']}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("NFT Bot with Mini App started!")
    def run_bot():
        bot.infinity_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
