import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID"))

# Marzban API
MARZBAN_API_URL = os.getenv("MARZBAN_API_URL")
MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")

# Server
SERVER_IP = os.getenv("SERVER_IP")

# Тарифы
BASE_TARIFF_GB = 200  # Базовый тариф: 200 ГБ
BASE_TARIFF_DAYS = 30  # Срок действия: 30 дней
BASE_TARIFF_PRICE = 249  # Цена базового тарифа: 249₽

EXTRA_GB_AMOUNT = 100  # Дополнительный пакет: 100 ГБ
EXTRA_GB_PRICE = 99  # Цена дополнительного пакета: 99₽

FREE_MODE_SPEED_MBPS = 2  # Скорость бесплатного режима: 2 Мбит/с

