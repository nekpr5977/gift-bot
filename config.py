# ========== НАСТРОЙКИ ==========
API_ID = 12345  # Получи на my.telegram.org
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_from_botfather"  # От @BotFather
ADMIN_ID = 123456789  # Твой Telegram ID

# Каналы для оповещений (можно оставить как есть)
CHANNELS = [
    -1001234567890,  # Основной канал
    -1009876543210,  # Резервный
]

# Параметры сканирования
SCAN_INTERVAL = 3  # Секунд между сканами
MIN_PROFIT_PERCENT = 10  # Минимальная прибыль для уведомления

# Список отслеживаемых фонов (все, которые есть в Gifts)
TRACKED_BACKGROUNDS = [
    "White", "Black", "Red", "Blue", "Green", "Yellow",
    "Purple", "Pink", "Orange", "Gray", "Brown", "Cyan",
    "Magenta", "Lime", "Teal", "Lavender", "Maroon",
    "Navy", "Olive", "Coral", "Gold", "Silver",
    "Midnight Blue", "Rainbow", "Monochrome"
]

# Цены для сравнения (в Stars)
PRICE_LEVELS = {
    "cheap": 10,
    "medium": 50,
    "expensive": 100,
    "ultra": 500
}
