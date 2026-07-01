import os
import json
import threading
from flask import Flask
from telebot import TeleBot, types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = TeleBot(TOKEN)
app = Flask(__name__)
DATA_FILE = "data.json"

# --- ЗАГРУЗКА И СОХРАНЕНИЕ ДАННЫХ ---
def load_data():
    if not os.path.exists(DATA_FILE):
        default = {"gifts": [], "users": {}}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- КОМАНДА /start ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("Статистика", callback_data="stats")
    markup.add(btn)
    bot.send_message(
        message.chat.id,
        "Привет! Я бот для продажи NFT подарков.\n\n"
        "Команды:\n"
        "/list - посмотреть товары\n"
        "/add_gift - добавить товар (админ)\n"
        "/buy ID - купить товар по ID",
        reply_markup=markup
    )

# --- КНОПКА СТАТИСТИКА ---
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats_callback(call):
    data = load_data()
    total = len(data["gifts"])
    bot.send_message(call.message.chat.id, f"Всего товаров: {total}")
    bot.answer_callback_query(call.id)

# --- КОМАНДА /list ---
@bot.message_handler(commands=['list'])
def list_gifts(message):
    data = load_data()
    if not data["gifts"]:
        bot.send_message(message.chat.id, "Товаров пока нет.")
        return
    text = "Список товаров:\n\n"
    for g in data["gifts"]:
        text += f"ID: {g['id']} | {g['name']} | {g['price']} руб.\n"
    bot.send_message(message.chat.id, text)

# --- КОМАНДА /add_gift (только админ) ---
@bot.message_handler(commands=['add_gift'])
def add_gift(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Нет прав.")
        return
    try:
        parts = message.text.split(maxsplit=1)[1].split("|")
        name = parts[0].strip()
        price = int(parts[1].strip())
        data = load_data()
        new_id = 1
        if data["gifts"]:
            new_id = max(g["id"] for g in data["gifts"]) + 1
        data["gifts"].append({"id": new_id, "name": name, "price": price})
        save_data(data)
        bot.reply_to(message, f"Товар '{name}' добавлен с ID {new_id} и ценой {price} руб.")
    except:
        bot.reply_to(message, "Формат: /add_gift Название | Цена")

# --- КОМАНДА /buy ---
@bot.message_handler(commands=['buy'])
def buy_gift(message):
    try:
        gift_id = int(message.text.split()[1])
        data = load_data()
        gift = next((g for g in data["gifts"] if g["id"] == gift_id), None)
        if not gift:
            bot.reply_to(message, "Товар не найден")
            return
        bot.reply_to(message, f"Вы выбрали '{gift['name']}' за {gift['price']} руб. (оплата в разработке)")
    except:
        bot.reply_to(message, "Формат: /buy ID")

# --- Flask (чтобы Render не ругался) ---
@app.route('/')
def home():
    return "NFT Bot is running!"

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("Бот запущен!")

    def run_bot():
        bot.infinity_polling()

    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
