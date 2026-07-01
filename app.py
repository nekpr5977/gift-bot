import os
import json
import time
import threading
from flask import Flask, request, jsonify
from telebot import TeleBot, types
from telebot.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost")

bot = TeleBot(TOKEN)
app = Flask(__name__)
DATA_FILE = "data.json"

# ========== БАЗА ДАННЫХ ==========
def load_data():
    if not os.path.exists(DATA_FILE):
        default = {
            "gifts": [
                {"id": 1, "name": "Алмазный дракон", "description": "Редкий NFT-дракон", "price_stars": 50, "price_rub": 250},
                {"id": 2, "name": "Золотая корона", "description": "Корона древнего короля", "price_stars": 30, "price_rub": 150},
                {"id": 3, "name": "Космический медведь", "description": "Медведь из другой галактики", "price_stars": 20, "price_rub": 100},
            ],
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

# ========== MINI APP (HTML) ==========
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
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .header h1 { font-size: 24px; background: linear-gradient(135deg, #f7971e, #ffd200); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .balance { background: #1a1a2e; padding: 8px 16px; border-radius: 20px; font-size: 14px; border: 1px solid #2a2a4e; }
        .gift { background: #1a1a2e; border-radius: 16px; padding: 16px; margin-bottom: 12px; border: 1px solid #2a2a4e; }
        .gift h3 { font-size: 18px; margin-bottom: 4px; }
        .gift p { color: #888; font-size: 14px; }
        .gift .price { color: #f7971e; font-weight: 700; margin-top: 8px; }
        .btn-buy { background: #f7971e; color: #000; border: none; padding: 10px 20px; border-radius: 12px; font-weight: 700; cursor: pointer; margin-top: 8px; width: 100%; }
        .btn-buy:active { transform: scale(0.97); }
        .btn-buy:disabled { opacity: 0.5; }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #1a1a2e; padding: 12px 24px; border-radius: 12px; border: 1px solid #2a2a4e; display: none; z-index: 999; }
        .toast.show { display: block; animation: slideUp 0.3s ease; }
        @keyframes slideUp { from { transform: translateX(-50%) translateY(20px); opacity: 0; } to { transform: translateX(-50%) translateY(0); opacity: 1; } }
        .loading { text-align: center; padding: 40px; color: #666; }
        .empty { text-align: center; color: #666; padding: 40px; }
    </style>
</head>
<body>
    <div id="app">
        <div class="header">
            <h1>🎁 NFT Store</h1>
            <div class="balance">⭐ <span id="balance">0</span></div>
        </div>
        <div id="gifts"><div class="loading">Загрузка...</div></div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        let userId = tg.initDataUnsafe?.user?.id || 'guest';
        let gifts = [];

        async function loadGifts() {
            try {
                const resp = await fetch('/api/gifts');
                const data = await resp.json();
                gifts = data.gifts || [];
                renderGifts();
            } catch(e) {
                document.getElementById('gifts').innerHTML = '<div class="empty">Ошибка загрузки</div>';
            }
        }

        function renderGifts() {
            const container = document.getElementById('gifts');
            if (gifts.length === 0) {
                container.innerHTML = '<div class="empty">Пока нет товаров</div>';
                return;
            }
            container.innerHTML = gifts.map(g => `
                <div class="gift">
                    <h3>${g.name}</h3>
                    <p>${g.description || ''}</p>
                    <div class="price">⭐ ${g.price_stars} / 💳 ${g.price_rub} руб.</div>
                    <button class="btn-buy" onclick="buyGift(${g.id})">Купить за ⭐</button>
                </div>
            `).join('');
        }

        function buyGift(giftId) {
            const gift = gifts.find(g => g.id === giftId);
            if (!gift) return;
            tg.sendData(JSON.stringify({ action: 'buy', gift_id: giftId }));
            showToast('⏳ Ожидание оплаты...');
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        loadGifts();
    </script>
</body>
</html>
"""

# ========== АВТО-СКУП (ИМИТАЦИЯ РЫНКА) ==========
def fetch_market_nfts():
    return [
        {"id": 101, "name": "Dragon", "price_stars": 5, "price_rub": 25},
        {"id": 102, "name": "Sword", "price_stars": 8, "price_rub": 40},
        {"id": 103, "name": "Shield", "price_stars": 12, "price_rub": 60},
    ]

def auto_buy_worker():
    AUTO_BUY_ENABLED = True
    MAX_PRICE_STARS = 10
    MARKUP_PERCENT = 30
    CHECK_INTERVAL = 30

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
                if nft["price_stars"] <= MAX_PRICE_STARS:
                    new_price_stars = int(nft["price_stars"] * (1 + MARKUP_PERCENT / 100))
                    new_price_rub = int(nft["price_rub"] * (1 + MARKUP_PERCENT / 100))
                    new_id = max([g["id"] for g in data["gifts"]] + [0]) + 1
                    data["gifts"].append({
                        "id": new_id,
                        "name": f"{nft['name']} (авто)",
                        "description": f"Куплен авто за {nft['price_stars']}⭐",
                        "price_stars": new_price_stars,
                        "price_rub": new_price_rub,
                        "market_id": nft["id"],
                        "bought_at": datetime.now().isoformat()
                    })
                    data["stats"]["total_bought"] += 1
                    data["stats"]["total_spent"] += nft["price_rub"]
                    save_data(data)
                    print(f"✅ Авто-скуп: {nft['name']} -> {new_price_stars}⭐")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Ошибка авто-скупа: {e}")
            time.sleep(CHECK_INTERVAL)

threading.Thread(target=auto_buy_worker, daemon=True).start()

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    web_app = types.WebAppInfo(f"https://{HOST}")
    btn_shop = types.InlineKeyboardButton("🛍 Открыть магазин", web_app=web_app)
    btn_stats = types.InlineKeyboardButton("📊 Статистика", callback_data="stats")
    btn_admin = types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin")
    markup.add(btn_shop, btn_stats, btn_admin)

    bot.send_message(
        message.chat.id,
        "🎁 *NFT Gift Store*\n\n"
        "Добро пожаловать в магазин цифровых подарков!\n"
        "Здесь можно купить уникальные NFT-подарки за Telegram Stars.\n\n"
        "💰 Оплата: Telegram Stars\n"
        "📦 Авто-скуп: включён (дешёвые NFT выкупаются автоматически)",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def show_stats(call):
    data = load_data()
    s = data["stats"]
    text = (
        "📊 *Статистика*\n\n"
        f"🛒 Куплено авто: {s['total_bought']}\n"
        f"💰 Продано: {s['total_sold']}\n"
        f"💸 Потрачено: {s['total_spent']}₽\n"
        f"💵 Заработано: {s['total_earned']}₽"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin")
def admin_panel(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа!", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📋 Список товаров", callback_data="admin_list"),
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add"),
        types.InlineKeyboardButton("🗑 Удалить товар", callback_data="admin_delete"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back")
    )
    bot.send_message(call.message.chat.id, "⚙️ *Админ-панель*", reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_list")
def admin_list(call):
    data = load_data()
    if not data["gifts"]:
        bot.send_message(call.message.chat.id, "📭 Товаров нет")
        return
    text = "📋 *Список товаров:*\n\n"
    for g in data["gifts"]:
        text += f"ID: `{g['id']}` | {g['name']} | ⭐ {g['price_stars']} | 💳 {g['price_rub']}₽\n"
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add")
def admin_add(call):
    bot.send_message(call.message.chat.id, "📝 Отправь команду:\n`/add_gift Название | Описание | Цена_Stars | Цена_рубли`", parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def admin_delete(call):
    bot.send_message(call.message.chat.id, "🗑 Отправь команду:\n`/del_gift ID`", parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back")
def back(call):
    start(call.message)
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['add_gift'])
def add_gift(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    try:
        parts = message.text.split(maxsplit=1)[1].split("|")
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        price_stars = int(parts[2].strip()) if len(parts) > 2 else 0
        price_rub = int(parts[3].strip()) if len(parts) > 3 else 0

        data = load_data()
        new_id = max([g["id"] for g in data["gifts"]] + [0]) + 1
        data["gifts"].append({
            "id": new_id,
            "name": name,
            "description": desc,
            "price_stars": price_stars,
            "price_rub": price_rub
        })
        save_data(data)
        bot.reply_to(message, f"✅ *{name}* добавлен!\n⭐ {price_stars} Stars\n💳 {price_rub} руб.", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Формат: `/add_gift Название | Описание | Цена_Stars | Цена_рубли`", parse_mode="Markdown")

@bot.message_handler(commands=['del_gift'])
def del_gift(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    try:
        gift_id = int(message.text.split()[1])
        data = load_data()
        data["gifts"] = [g for g in data["gifts"] if g["id"] != gift_id]
        save_data(data)
        bot.reply_to(message, f"✅ Товар с ID {gift_id} удалён")
    except:
        bot.reply_to(message, "❌ Формат: `/del_gift ID`", parse_mode="Markdown")

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        gift_id = data.get("gift_id")

        if action == "buy":
            store = load_data()
            gift = next((g for g in store["gifts"] if g["id"] == gift_id), None)
            if not gift:
                bot.send_message(message.chat.id, "❌ Подарок не найден")
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
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

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
    bot.send_message(message.chat.id, f"🎉 Ты купил *{gift['name']}*!", parse_mode="Markdown")

# ========== API ДЛЯ MINI APP ==========
@app.route('/')
def index():
    return HTML_PAGE

@app.route('/api/gifts')
def api_gifts():
    data = load_data()
    return jsonify({"gifts": data["gifts"]})

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 NFT Bot with Mini App started!")
    def run_bot():
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
