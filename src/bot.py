import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import ALLOWED_CHAT_IDS, SERVERS_BY_ID
import src.monitor as monitor
import src.servers as servers
import src.session as session

logger = logging.getLogger(__name__)

router = Router()


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
            logger.warning(
                f"Unauthorized access attempt by user {user.full_name} (ID: {user.id})"
            )
        return is_admin


router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def make_progress_bar(percent: float, length: int = 10) -> str:
    filled = max(0, min(length, int(round(percent / 100 * length))))
    return "█" * filled + "░" * (length - filled)


def build_servers_keyboard():
    builder = InlineKeyboardBuilder()
    for srv in servers.list_servers():
        builder.button(text=f"🖥 {srv.name}", callback_data=f"srv:{srv.id}")
    builder.adjust(1)
    return builder.as_markup()


def build_main_keyboard(server_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Check VPS Status", callback_data=f"{server_id}:status")
    builder.button(text="🐳 Check Docker Status", callback_data=f"{server_id}:docker")
    builder.button(text="🔄 Restart VPS", callback_data=f"{server_id}:confirm_reboot")
    builder.button(text="⛔ Shutdown VPS", callback_data=f"{server_id}:confirm_shutdown")
    builder.button(text="🐳 Restart Docker Service", callback_data=f"{server_id}:confirm_docker")
    builder.button(text="⬅️ Servers", callback_data="servers")
    builder.adjust(1)
    return builder.as_markup()


def format_status_text(server_id: str, status: dict) -> str:
    uptime_str = monitor.format_uptime(status["uptime"])
    cpu_bar = make_progress_bar(status["cpu_percent"])
    ram_bar = make_progress_bar(status["ram_percent"])
    disk_bar = make_progress_bar(status["disk_percent"])

    temp_str = f"{status['cpu_temp']:.1f}°C" if status.get("cpu_temp") is not None else "N/A"
    load = status.get("load_avg")
    if load:
        load_str = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
    else:
        load_str = "N/A"

    return (
        f"📊 **{server_id} SYSTEM STATUS**\n"
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


def servers_list_text() -> str:
    names = ", ".join(s.name for s in servers.list_servers()) or "none"
    return (
        "👋 **VPS Monitoring Bot**\n\n"
        f"Select a server:\n`{names}`"
    )


def panel_text(server_id: str) -> str:
    return f"👋 **{server_id} Control Panel:**"


async def show_servers_list(target: types.Message, *, edit: bool = False) -> None:
    text = servers_list_text()
    markup = build_servers_keyboard()
    if edit:
        await target.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="Markdown")


async def show_server_panel(
    target: types.Message,
    chat_id: int,
    server_id: str,
    *,
    edit: bool = False,
) -> None:
    if server_id not in SERVERS_BY_ID:
        await show_servers_list(target, edit=edit)
        return
    session.set_last_server(chat_id, server_id, view="panel")
    text = panel_text(server_id)
    markup = build_main_keyboard(server_id)
    if edit:
        await target.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="Markdown")


def _parse_server_action(data: str) -> tuple[str, str] | None:
    """Parse 'SERVER:action' callback data."""
    if ":" not in data:
        return None
    server_id, action = data.split(":", 1)
    if server_id not in SERVERS_BY_ID:
        return None
    return server_id, action


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    last = session.get_last_server_id(message.chat.id)
    if last and last in SERVERS_BY_ID:
        await show_server_panel(message, message.chat.id, last, edit=False)
        return
    await show_servers_list(message, edit=False)


@router.message(Command("status"))
async def cmd_status(message: types.Message):
    last = session.get_last_server_id(message.chat.id)
    server_id = last if last and last in SERVERS_BY_ID else None
    if not server_id:
        await show_servers_list(message, edit=False)
        return
    try:
        status = await servers.get_system_status(server_id)
        text = format_status_text(server_id, status)
    except Exception as e:
        logger.error(f"Status failed for {server_id}: {e}")
        text = f"❌ Failed to fetch status for **{server_id}**:\n`{e}`"
    await message.answer(text, reply_markup=build_main_keyboard(server_id), parse_mode="Markdown")


@router.callback_query(F.data == "servers")
async def cb_servers(callback: types.CallbackQuery):
    await show_servers_list(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("srv:"))
async def cb_select_server(callback: types.CallbackQuery):
    server_id = callback.data.split(":", 1)[1]
    await show_server_panel(callback.message, callback.from_user.id, server_id, edit=True)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:status$"))
async def cb_status(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    session.set_last_server(callback.from_user.id, server_id, view="status")
    try:
        status = await servers.get_system_status(server_id)
        text = format_status_text(server_id, status)
    except Exception as e:
        logger.error(f"Status failed for {server_id}: {e}")
        text = f"❌ Failed to fetch status for **{server_id}**:\n`{e}`"
    await callback.message.edit_text(
        text, reply_markup=build_main_keyboard(server_id), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:docker$"))
async def cb_docker_status(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    session.set_last_server(callback.from_user.id, server_id, view="docker")
    docker_info = await servers.get_docker_status_info(server_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Back", callback_data=f"srv:{server_id}")

    await callback.message.edit_text(
        docker_info, reply_markup=builder.as_markup(), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:confirm_reboot$"))
async def cb_confirm_reboot(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Yes, RESTART VPS", callback_data=f"{server_id}:action_reboot")
    builder.button(text="❌ Cancel", callback_data=f"srv:{server_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        f"⚠️ **Are you sure you want to RESTART {server_id}?**\n\n"
        "This will reboot the physical/virtual host server.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:confirm_shutdown$"))
async def cb_confirm_shutdown(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    builder = InlineKeyboardBuilder()
    builder.button(text="🚨 Yes, SHUTDOWN VPS", callback_data=f"{server_id}:action_shutdown")
    builder.button(text="❌ Cancel", callback_data=f"srv:{server_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        f"🚨 **WARNING: SHUTDOWN {server_id}** 🚨\n\n"
        "Are you sure you want to power off the VPS? "
        "You will not be able to turn it back on unless you use your VPS provider's control panel!",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:confirm_docker$"))
async def cb_confirm_docker(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    builder = InlineKeyboardBuilder()
    builder.button(text="🐳 Yes, RESTART DOCKER", callback_data=f"{server_id}:action_docker")
    builder.button(text="❌ Cancel", callback_data=f"srv:{server_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        f"🐳 **Are you sure you want to RESTART Docker on {server_id}?**\n\n"
        "This will restart the Docker daemon. **All running containers may stop.**\n"
        "Containers with a restart policy will start again when Docker is ready.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:action_reboot$"))
async def cb_action_reboot(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    await callback.message.edit_text(f"⏳ Sending reboot command to **{server_id}**...")
    success, msg = await servers.reboot_vps(server_id)
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}", parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:action_shutdown$"))
async def cb_action_shutdown(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    await callback.message.edit_text(f"⏳ Sending shutdown command to **{server_id}**...")
    success, msg = await servers.shutdown_vps(server_id)
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}", parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^[^:]+:action_docker$"))
async def cb_action_docker(callback: types.CallbackQuery):
    parsed = _parse_server_action(callback.data)
    if not parsed:
        await callback.answer("Unknown server", show_alert=True)
        return
    server_id, _ = parsed
    await callback.message.edit_text(f"⏳ Sending Docker restart command to **{server_id}**...")
    success, msg = await servers.restart_docker(server_id)
    await callback.message.edit_text(f"{'✅' if success else '❌'} {msg}", parse_mode="Markdown")
    await callback.answer()

def get_dispatcher(bot: Bot) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
