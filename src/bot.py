import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.config import ALLOWED_CHAT_IDS, TELEGRAM_BOT_TOKEN
import src.monitor as monitor
import src.utils as utils

logger = logging.getLogger(__name__)

# Initialize router
router = Router()

# Custom filter to verify admin user
class AdminFilter(BaseFilter):
    async def __call__(self, event: types.TelegramObject) -> bool:
        user = None
        if isinstance(event, types.Message):
            user = event.from_user
        elif isinstance(event, types.CallbackQuery):
            user = event.from_user
            
        if not user:
            return False
            
        is_admin = user.id in ALLOWED_CHAT_IDS
        if not is_admin:
            logger.warning(f"Unauthorized access attempt by user {user.full_name} (ID: {user.id})")
        return is_admin

# Apply AdminFilter to all routes in this router
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

def make_progress_bar(percent: float, length: int = 10) -> str:
    """Creates a beautiful text-based progress bar."""
    filled = max(0, min(length, int(round(percent / 100 * length))))
    return "█" * filled + "░" * (length - filled)

def build_main_keyboard():
    """Builds the main control panel keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Check VPS Status", callback_data="status")
    builder.button(text="🐳 Check Docker Status", callback_data="docker_status")
    builder.button(text="🔄 Restart VPS", callback_data="confirm_reboot")
    builder.button(text="⛔ Shutdown VPS", callback_data="confirm_shutdown")
    builder.button(text="🐳 Restart Docker Service", callback_data="confirm_docker")
    # Arrange buttons: Status buttons on top, actions below
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()

def get_status_text() -> str:
    """Collects and formats system status."""
    status = monitor.get_system_status()
    uptime_str = monitor.format_uptime(status["uptime"])
    
    cpu_bar = make_progress_bar(status["cpu_percent"])
    ram_bar = make_progress_bar(status["ram_percent"])
    disk_bar = make_progress_bar(status["disk_percent"])
    
    temp_str = f"{status['cpu_temp']:.1f}°C" if status["cpu_temp"] is not None else "N/A"
    
    if status["load_avg"]:
        load_str = f"{status['load_avg'][0]:.2f}, {status['load_avg'][1]:.2f}, {status['load_avg'][2]:.2f}"
    else:
        load_str = "N/A"
        
    text = (
        f"📊 **VPS SYSTEM STATUS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ **Uptime:** `{uptime_str}`\n"
        f"🧠 **Load Average:** `{load_str}`\n"
        f"🌡️ **CPU Temp:** `{temp_str}`\n\n"
        f"💻 **CPU Usage:** `[{cpu_bar}] {status['cpu_percent']:.1f}%`\n"
        f"📟 **RAM Usage:** `[{ram_bar}] {status['ram_percent']:.1f}%` "
        f"({status['ram_used_gb']:.1f} / {status['ram_total_gb']:.1f} GB)\n"
        f"💾 **Disk Space:** `[{disk_bar}] {status['disk_percent']:.1f}%` "
        f"({status['disk_used_gb']:.1f} / {status['disk_total_gb']:.1f} GB)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    return text

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handles the /start command."""
    await message.answer(
        "👋 **Welcome to VPS Monitoring Bot!**\n\n"
        "Here is your control panel:",
        reply_markup=build_main_keyboard(),
        parse_mode="Markdown"
    )

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    """Handles the /status command."""
    text = get_status_text()
    await message.answer(text, reply_markup=build_main_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "status")
async def cb_status(callback: types.CallbackQuery):
    """Callback for checking status."""
    text = get_status_text()
    # Edit the text and keep the main menu keyboard
    await callback.message.edit_text(
        text, 
        reply_markup=build_main_keyboard(), 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "docker_status")
async def cb_docker_status(callback: types.CallbackQuery):
    """Callback for checking docker container list."""
    docker_info = utils.get_docker_status_info()
    
    # Back button to return to main menu
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Back", callback_data="back_to_menu")
    
    await callback.message.edit_text(
        docker_info,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: types.CallbackQuery):
    """Returns to the main control panel."""
    await callback.message.edit_text(
        "👋 **VPS Control Panel:**",
        reply_markup=build_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# CONFIRMATIONS
@router.callback_query(F.data == "confirm_reboot")
async def cb_confirm_reboot(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Yes, RESTART VPS", callback_data="action_reboot")
    builder.button(text="❌ Cancel", callback_data="back_to_menu")
    builder.adjust(1, 1)
    
    await callback.message.edit_text(
        "⚠️ **Are you sure you want to RESTART the VPS?**\n\n"
        "This will reboot the physical/virtual host server.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_shutdown")
async def cb_confirm_shutdown(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🚨 Yes, SHUTDOWN VPS", callback_data="action_shutdown")
    builder.button(text="❌ Cancel", callback_data="back_to_menu")
    builder.adjust(1, 1)
    
    await callback.message.edit_text(
        "🚨 **WARNING: SHUTDOWN VPS** 🚨\n\n"
        "Are you sure you want to power off the VPS? "
        "You will not be able to turn it back on unless you use your VPS provider's control panel!",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_docker")
async def cb_confirm_docker(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🐳 Yes, RESTART DOCKER", callback_data="action_docker")
    builder.button(text="❌ Cancel", callback_data="back_to_menu")
    builder.adjust(1, 1)
    
    await callback.message.edit_text(
        "🐳 **Are you sure you want to RESTART Docker?**\n\n"
        "This will restart the Docker daemon. **All running containers, including this bot, will stop.**\n"
        "If this container has a restart policy (e.g. `restart: always`), it will start up automatically when Docker is ready.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ACTIONS
@router.callback_query(F.data == "action_reboot")
async def cb_action_reboot(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ Sending reboot command...")
    success, msg = utils.reboot_vps()
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}")
    await callback.answer()

@router.callback_query(F.data == "action_shutdown")
async def cb_action_shutdown(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ Sending shutdown command...")
    success, msg = utils.shutdown_vps()
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}")
    await callback.answer()

@router.callback_query(F.data == "action_docker")
async def cb_action_docker(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ Sending Docker restart command...")
    success, msg = utils.restart_docker()
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}")
    await callback.answer()

def get_dispatcher(bot: Bot) -> Dispatcher:
    """Returns configured dispatcher."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp
