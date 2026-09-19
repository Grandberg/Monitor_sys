import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# App mode: "bot" (Telegram + monitoring) is the only runtime for now
APP_MODE = os.getenv("APP_MODE", "bot").strip().lower()

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if APP_MODE == "bot" and not TELEGRAM_BOT_TOKEN:
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

if APP_MODE == "bot" and not ALLOWED_CHAT_IDS:
    print("Warning: ALLOWED_CHAT_IDS is empty! Nobody will receive alerts or be able to control the VPS.")

# Resource Thresholds
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "85"))
RAM_THRESHOLD = float(os.getenv("RAM_THRESHOLD", "85"))
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", "90"))

# Intervals & Cooldowns
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "1800"))
CPU_ALERT_DELAY = int(os.getenv("CPU_ALERT_DELAY", "300"))
RAM_ALERT_DELAY = int(os.getenv("RAM_ALERT_DELAY", "300"))

# Host Paths (local / Docker-on-host mounts)
HOST_ROOT_PATH = os.getenv("HOST_ROOT_PATH", "/host/root")
PROCFS_PATH = os.getenv("PROCFS_PATH", "/host/proc")

if os.path.exists(PROCFS_PATH):
    os.environ["PROCFS_PATH"] = PROCFS_PATH

# Session persistence (last selected server per chat)
SESSION_STORE_PATH = os.getenv("SESSION_STORE_PATH", "/data/sessions.json")

# Default SSH key path used by remote servers unless overridden per-server
DEFAULT_SSH_KEY_PATH = os.getenv("DEFAULT_SSH_KEY_PATH", "/keys/id_ed25519_monitor_myor")


@dataclass(frozen=True)
class ServerConfig:
    id: str
    name: str
    type: str  # "local" | "ssh"
    host: Optional[str] = None
    port: int = 22
    user: Optional[str] = None
    key_path: Optional[str] = None


def _parse_servers() -> list[ServerConfig]:
    """
    SERVERS env format (comma-separated entries):
      MY107|local
      MYOR|ssh|opc@92.5.8.212:22|/keys/id_ed25519_monitor_myor

    Fields for ssh: id|ssh|user@host[:port]|[key_path]
    """
    raw = os.getenv(
        "SERVERS",
        "MY107|local,MYOR|ssh|opc@92.5.8.212:22|/keys/id_ed25519_monitor_myor",
    ).strip()
    servers: list[ServerConfig] = []
    if not raw:
        return servers

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) < 2:
            print(f"Warning: invalid SERVERS entry '{entry}', skipping")
            continue
        sid, stype = parts[0], parts[1].lower()
        if stype == "local":
            servers.append(ServerConfig(id=sid, name=sid, type="local"))
            continue
        if stype == "ssh":
            if len(parts) < 3:
                print(f"Warning: ssh server '{sid}' missing user@host, skipping")
                continue
            target = parts[2]
            key_path = parts[3] if len(parts) > 3 and parts[3] else DEFAULT_SSH_KEY_PATH
            user_host, _, port_str = target.partition(":")
            if "@" not in user_host:
                print(f"Warning: ssh server '{sid}' must be user@host, skipping")
                continue
            user, host = user_host.split("@", 1)
            port = int(port_str) if port_str else 22
            servers.append(
                ServerConfig(
                    id=sid,
                    name=sid,
                    type="ssh",
                    host=host,
                    port=port,
                    user=user,
                    key_path=key_path,
                )
            )
            continue
        print(f"Warning: unknown server type '{stype}' for '{sid}', skipping")

    return servers


SERVERS: list[ServerConfig] = _parse_servers()
SERVERS_BY_ID: dict[str, ServerConfig] = {s.id: s for s in SERVERS}

if not SERVERS:
    print("Warning: SERVERS is empty — bot will have no targets.")
