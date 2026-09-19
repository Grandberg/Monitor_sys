import asyncio
import logging
import time
from aiogram import Bot

from src.config import (
    TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS,
    CPU_THRESHOLD,
    RAM_THRESHOLD,
    DISK_THRESHOLD,
    CHECK_INTERVAL,
    ALERT_COOLDOWN,
    CPU_ALERT_DELAY,
    RAM_ALERT_DELAY,
)
import src.servers as servers
from src.bot import get_dispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _new_alert_state() -> dict:
    return {
        "last_alert_time": {"cpu": 0.0, "ram": 0.0, "disk": 0.0},
        "alert_active": {"cpu": False, "ram": False, "disk": False},
        "spike_start_time": {"cpu": None, "ram": None},
    }


async def _send_admins(bot: Bot, msg: str) -> None:
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await bot.send_message(chat_id, msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")


async def monitoring_task(bot: Bot):
    """Periodically monitors all configured servers and sends alerts."""
    logger.info("Starting multi-server resource monitoring loop...")
    states = {srv.id: _new_alert_state() for srv in servers.list_servers()}

    while True:
        for srv in servers.list_servers():
            if srv.id not in states:
                states[srv.id] = _new_alert_state()
            state = states[srv.id]
            try:
                status = await servers.get_system_status(srv.id)
                current_time = time.time()
                label = srv.name

                # --- CPU ---
                cpu = status["cpu_percent"]
                if cpu > CPU_THRESHOLD:
                    if state["spike_start_time"]["cpu"] is None:
                        state["spike_start_time"]["cpu"] = current_time
                        logger.info(
                            f"[{label}] CPU threshold exceeded ({cpu}% > {CPU_THRESHOLD}%). Starting delay..."
                        )
                    elapsed = current_time - state["spike_start_time"]["cpu"]
                    if elapsed >= CPU_ALERT_DELAY:
                        if not state["alert_active"]["cpu"] or (
                            current_time - state["last_alert_time"]["cpu"] > ALERT_COOLDOWN
                        ):
                            await _send_admins(
                                bot,
                                f"🚨 **RESOURCE ALERT: CPU [{label}]** 🚨\n\n"
                                f"⚠️ CPU usage is at **{cpu:.1f}%** (threshold: {CPU_THRESHOLD}%)\n"
                                f"⏱️ Duration: continuously high for {int(elapsed)} seconds",
                            )
                            state["alert_active"]["cpu"] = True
                            state["last_alert_time"]["cpu"] = current_time
                else:
                    if state["spike_start_time"]["cpu"] is not None:
                        logger.info(f"[{label}] CPU back under threshold ({cpu}%).")
                    state["spike_start_time"]["cpu"] = None
                    if state["alert_active"]["cpu"]:
                        await _send_admins(
                            bot,
                            f"✅ **RECOVERY: CPU [{label}]** ✅\n\n"
                            f"CPU usage went back to normal: **{cpu:.1f}%**",
                        )
                        state["alert_active"]["cpu"] = False

                # --- RAM ---
                ram = status["ram_percent"]
                if ram > RAM_THRESHOLD:
                    if state["spike_start_time"]["ram"] is None:
                        state["spike_start_time"]["ram"] = current_time
                        logger.info(
                            f"[{label}] RAM threshold exceeded ({ram}% > {RAM_THRESHOLD}%). Starting delay..."
                        )
                    elapsed = current_time - state["spike_start_time"]["ram"]
                    if elapsed >= RAM_ALERT_DELAY:
                        if not state["alert_active"]["ram"] or (
                            current_time - state["last_alert_time"]["ram"] > ALERT_COOLDOWN
                        ):
                            await _send_admins(
                                bot,
                                f"🚨 **RESOURCE ALERT: RAM [{label}]** 🚨\n\n"
                                f"⚠️ Memory usage is at **{ram:.1f}%** (threshold: {RAM_THRESHOLD}%)\n"
                                f"Used: `{status['ram_used_gb']:.1f} GB` / Total: `{status['ram_total_gb']:.1f} GB`\n"
                                f"⏱️ Duration: continuously high for {int(elapsed)} seconds",
                            )
                            state["alert_active"]["ram"] = True
                            state["last_alert_time"]["ram"] = current_time
                else:
                    if state["spike_start_time"]["ram"] is not None:
                        logger.info(f"[{label}] RAM back under threshold ({ram}%).")
                    state["spike_start_time"]["ram"] = None
                    if state["alert_active"]["ram"]:
                        await _send_admins(
                            bot,
                            f"✅ **RECOVERY: RAM [{label}]** ✅\n\n"
                            f"Memory usage went back to normal: **{ram:.1f}%**",
                        )
                        state["alert_active"]["ram"] = False

                # --- Disk ---
                disk = status["disk_percent"]
                if disk > DISK_THRESHOLD:
                    if not state["alert_active"]["disk"] or (
                        current_time - state["last_alert_time"]["disk"] > ALERT_COOLDOWN
                    ):
                        await _send_admins(
                            bot,
                            f"🚨 **RESOURCE ALERT: DISK [{label}]** 🚨\n\n"
                            f"⚠️ Disk space usage is at **{disk:.1f}%** (threshold: {DISK_THRESHOLD}%)\n"
                            f"Used: `{status['disk_used_gb']:.1f} GB` / Total: `{status['disk_total_gb']:.1f} GB`",
                        )
                        state["alert_active"]["disk"] = True
                        state["last_alert_time"]["disk"] = current_time
                else:
                    if state["alert_active"]["disk"]:
                        await _send_admins(
                            bot,
                            f"✅ **RECOVERY: DISK [{label}]** ✅\n\n"
                            f"Disk space usage went back to normal: **{disk:.1f}%**",
                        )
                        state["alert_active"]["disk"] = False

            except Exception as e:
                logger.error(f"Error monitoring {srv.id}: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)


async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = get_dispatcher(bot)

    server_names = ", ".join(s.name for s in servers.list_servers()) or "none"
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id,
                "🚀 **VPS Monitoring Bot has started successfully!**\n"
                f"Servers: `{server_names}`\n"
                "Use `/start` to open the control panel.",
                parse_mode="Markdown",
            )
            logger.info(f"Sent startup message to admin ID: {chat_id}")
        except Exception as e:
            logger.error(f"Could not send startup message to {chat_id}: {e}")

    logger.info("Starting Telegram Bot long-polling...")
    try:
        await asyncio.gather(dp.start_polling(bot), monitoring_task(bot))
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Monitoring application stopped.")
