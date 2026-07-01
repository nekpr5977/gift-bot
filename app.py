import os
from flask import Flask
from telebot import TeleBot

TOKEN = os.getenv("BOT_TOKEN")
ADMIN = os.getenv("ADMIN_ID")

bot = TeleBot(TOKEN)
app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я живой!")

@app.route('/')
def home():
    return "Бот работает!"

if __name__ == "__main__":
    import threading
    def run_bot():
        bot.infinity_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
