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

