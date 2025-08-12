import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH") or ""
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
DEFAULT_URL = os.getenv("DEFAULT_URL") or "https://qepd.co.ir/fa-IR/DouranPortal/6423/page/%D8%AE%D8%A7%D9%85%D9%88%D8%B4%DB%8C-%D9%87%D8%A7"
CRAWL_INTERVAL_MIN = int(os.getenv("CRAWL_INTERVAL_MIN", "10"))

# Logging
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "5242880"))  # 5 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Proxy (keep your working setup)
PROXY = ("socks5", os.getenv("SOCKS_HOST", "127.0.0.1"), int(os.getenv("SOCKS_PORT", "10808")), True)

DB_PATH = os.path.abspath(os.getenv("DB_PATH", "bot.db"))
LAST_UPDATE_SELECTOR_ID = "LastUpdatePortalCtrl"
