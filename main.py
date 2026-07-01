import asyncio
import json
import sqlite3
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

from config import *

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('gifts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS gifts
                 (id TEXT PRIMARY KEY, name TEXT, background TEXT, model TEXT, 
                  price INT, found_at TIMESTAMP, sold BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

def add_gift(gift_id, name, background, model, price):
    conn = sqlite3.connect('gifts.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO gifts VALUES (?, ?, ?, ?, ?, ?, 0)",
              (gift_id, name, background, model, price, datetime.now()))
    conn.commit()
    conn.close()

def get_gift(gift_id):
    conn = sqlite3.connect('gifts.db')
    c = conn.cursor()
    c.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
    result = c.fetchone()
    conn.close()
    return result

def mark_sold(gift_id):
    conn = sqlite3.connect('gifts.db')
    c = conn.cursor()
    c.execute("UPDATE gifts SET sold = 1 WHERE id = ?", (gift_id,))
    conn.commit()
    conn.close()

# ========== КЛИЕНТ TELEGRAM ==========
app = Client("gift_sniper", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ========== СПИСОК ДОСТУПНЫХ ПОДАРКОВ ==========
async def get_available_gifts():
    """Получает список доступных для покупки подарков"""
    async with aiohttp.ClientSession() as session:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # Здесь должен быть реальный API запрос к Telegram Gifts
        # Пока используем тестовые данные
        return [
            {"id": "1", "name": "Dragon", "background": "Red", "model": "Premium", "price": 25},
            {"id": "2", "name": "Crown", "background": "Gold", "model": "Limited", "price": 50},
            {"id": "3", "name": "Bear", "background": "Midnight Blue", "model": "Rare", "price": 10},
        ]

# ========== АНАЛИЗ ЦЕН ==========
def analyze_gift(gift):
    """Анализирует подарок и возвращает потенциал прибыли"""
    # Здесь будет реальная логика анализа
    # Сравниваем цену с рыночной
    market_price = 0
    if gift["background"] in ["Midnight Blue", "Rainbow", "Gold"]:
        market_price = gift["price"] * 3
    elif gift["model"] in ["Premium", "Limited", "Rare"]:
        market_price = gift["price"] * 2
    else:
        market_price = gift["price"] * 1.2
    
    profit_percent = ((market_price - gift["price"]) / gift["price"]) * 100
    return market_price, profit_percent

# ========== ОПОВЕЩЕНИЯ ==========
async def send_alert(gift, market_price, profit_percent):
    """Отправляет уведомление о найденном подарке"""
    text = f"""
🎁 *{gift['name']}*

📊 *Анализ:*
├ Редкость: {gift['background']} / {gift['model']}
├ Цена покупки: {gift['price']} ⭐
├ Рыночная цена: {market_price:.0f} ⭐
└ Потенциальная прибыль: {profit_percent:.1f}%

💡 *Это выгодная сделка!*
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Открыть на Portals", url=f"https://portals.gift/gift/{gift['id']}")],
        [InlineKeyboardButton("💰 Купить сейчас", callback_data=f"buy_{gift['id']}")]
    ])
    
    for chat_id in CHANNELS + [ADMIN_ID]:
        try:
            await app.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")
        except:
            pass

# ========== КОМАНДЫ БОТА ==========
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "🎯 *Gift Sniper Bot*\n\n"
        "Я мониторю рынок NFT-подарков в реальном времени.\n"
        "Как только нахожу выгодное предложение — присылаю уведомление.\n\n"
        "Команды:\n"
        "/stats — статистика\n"
        "/status — статус сканера\n"
        "/help — помощь",
        parse_mode="Markdown"
    )

@app.on_message(filters.command("stats"))
async def stats(client, message):
    conn = sqlite3.connect('gifts.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM gifts")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM gifts WHERE sold = 1")
    sold = c.fetchone()[0]
    conn.close()
    
    await message.reply(
        f"📊 *Статистика*\n\n"
        f"📦 Найдено подарков: {total}\n"
        f"💰 Куплено: {sold}\n"
        f"🔄 В обработке: {total - sold}",
        parse_mode="Markdown"
    )

@app.on_callback_query()
async def handle_callback(client, callback_query):
    if callback_query.data.startswith("buy_"):
        gift_id = callback_query.data.split("_")[1]
        gift = get_gift(gift_id)
        if not gift:
            await callback_query.answer("Подарок уже куплен или не найден!", show_alert=True)
            return
        
        await callback_query.answer("✅ Подарок отмечен как купленный!", show_alert=True)
        mark_sold(gift_id)
        
        # Логируем покупку
        with open("purchases.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {gift[1]} за {gift[4]} ⭐\n")

# ========== ФОНОВОЕ СКАНИРОВАНИЕ ==========
async def scanner():
    """Фоновый сканер, который мониторит рынок"""
    print("🔍 Сканер запущен...")
    
    while True:
        try:
            gifts = await get_available_gifts()
            
            for gift in gifts:
                # Проверяем, не обработали ли уже этот подарок
                existing = get_gift(gift["id"])
                if existing:
                    continue
                
                # Анализируем
                market_price, profit_percent = analyze_gift(gift)
                
                # Если прибыль выше порога — отправляем уведомление
                if profit_percent >= MIN_PROFIT_PERCENT:
                    add_gift(gift["id"], gift["name"], gift["background"], 
                            gift["model"], gift["price"])
                    await send_alert(gift, market_price, profit_percent)
                    print(f"🎯 Найден выгодный подарок: {gift['name']} ({profit_percent:.1f}%)")
            
            await asyncio.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            print(f"❌ Ошибка сканера: {e}")
            await asyncio.sleep(SCAN_INTERVAL * 2)

# ========== ЗАПУСК ==========
async def main():
    init_db()
    print("🚀 Gift Sniper Bot запущен!")
    
    # Запускаем сканер в фоне
    asyncio.create_task(scanner())
    
    # Запускаем бота
    await app.start()
    print("✅ Бот готов к работе!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
