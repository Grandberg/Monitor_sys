import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables!")

# Allowed Chat IDs for alerts and commands
allowed_chats_str = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS = []
if allowed_chats_str:
    for chat_id in allowed_chats_str.split(","):
        chat_id = chat_id.strip()
        if chat_id:
            try:
                ALLOWED_CHAT_IDS.append(int(chat_id))
            except ValueError:
                print(f"Warning: Invalid chat ID in ALLOWED_CHAT_IDS: '{chat_id}'")

if not ALLOWED_CHAT_IDS:
    print("Warning: ALLOWED_CHAT_IDS is empty! Nobody will receive alerts or be able to control the VPS.")

# Resource Thresholds
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "85"))
RAM_THRESHOLD = float(os.getenv("RAM_THRESHOLD", "85"))
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", "90"))

# Intervals & Cooldowns
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "1800"))

# Host Paths
HOST_ROOT_PATH = os.getenv("HOST_ROOT_PATH", "/host/root")
PROCFS_PATH = os.getenv("PROCFS_PATH", "/host/proc")

# Ensure psutil uses the mounted proc filesystem if specified
if os.path.exists(PROCFS_PATH):
    os.environ["PROCFS_PATH"] = PROCFS_PATH
