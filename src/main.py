import asyncio
import logging
import time
from aiogram import Bot
from src.config import (
    TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS,
    CPU_THRESHOLD, RAM_THRESHOLD, DISK_THRESHOLD,
    CHECK_INTERVAL, ALERT_COOLDOWN,
    CPU_ALERT_DELAY, RAM_ALERT_DELAY
)
import src.monitor as monitor
from src.bot import get_dispatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def monitoring_task(bot: Bot):
    """Periodically monitors host resources and sends alerts to admins."""
    logger.info("Starting host resource monitoring loop...")
    
    # State tracking for alerts
    last_alert_time = {"cpu": 0.0, "ram": 0.0, "disk": 0.0}
    alert_active = {"cpu": False, "ram": False, "disk": False}
    
    # Spike start times (records when the threshold was first crossed)
    spike_start_time = {"cpu": None, "ram": None}
    
    while True:
        try:
            status = monitor.get_system_status()
            current_time = time.time()
            
            # --- Check CPU ---
            cpu = status["cpu_percent"]
            if cpu > CPU_THRESHOLD:
                if spike_start_time["cpu"] is None:
                    spike_start_time["cpu"] = current_time
                    logger.info(f"CPU threshold exceeded ({cpu}% > {CPU_THRESHOLD}%). Starting delay timer...")
                
                elapsed = current_time - spike_start_time["cpu"]
                if elapsed >= CPU_ALERT_DELAY:
                    if not alert_active["cpu"] or (current_time - last_alert_time["cpu"] > ALERT_COOLDOWN):
                        msg = (
                            f"🚨 **RESOURCE ALERT: CPU** 🚨\n\n"
                            f"⚠️ CPU usage is at **{cpu:.1f}%** (threshold: {CPU_THRESHOLD}%)\n"
                            f"⏱️ Duration: continuously high for {int(elapsed)} seconds"
                        )
                        for chat_id in ALLOWED_CHAT_IDS:
                            try:
                                await bot.send_message(chat_id, msg, parse_mode="Markdown")
                            except Exception as e:
                                logger.error(f"Failed to send alert to {chat_id}: {e}")
                        alert_active["cpu"] = True
                        last_alert_time["cpu"] = current_time
            else:
                if spike_start_time["cpu"] is not None:
                    logger.info(f"CPU usage went below threshold ({cpu}% <= {CPU_THRESHOLD}%). Resetting delay timer.")
                spike_start_time["cpu"] = None
                if alert_active["cpu"]:
                    msg = f"✅ **RECOVERY: CPU** ✅\n\nCPU usage went back to normal: **{cpu:.1f}%**"
                    for chat_id in ALLOWED_CHAT_IDS:
                        try:
                            await bot.send_message(chat_id, msg, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to send recovery to {chat_id}: {e}")
                    alert_active["cpu"] = False

            # --- Check RAM ---
            ram = status["ram_percent"]
            if ram > RAM_THRESHOLD:
                if spike_start_time["ram"] is None:
                    spike_start_time["ram"] = current_time
                    logger.info(f"RAM threshold exceeded ({ram}% > {RAM_THRESHOLD}%). Starting delay timer...")
                
                elapsed = current_time - spike_start_time["ram"]
                if elapsed >= RAM_ALERT_DELAY:
                    if not alert_active["ram"] or (current_time - last_alert_time["ram"] > ALERT_COOLDOWN):
                        msg = (
                            f"🚨 **RESOURCE ALERT: RAM** 🚨\n\n"
                            f"⚠️ Memory usage is at **{ram:.1f}%** (threshold: {RAM_THRESHOLD}%)\n"
                            f"Used: `{status['ram_used_gb']:.1f} GB` / Total: `{status['ram_total_gb']:.1f} GB`\n"
                            f"⏱️ Duration: continuously high for {int(elapsed)} seconds"
                        )
                        for chat_id in ALLOWED_CHAT_IDS:
                            try:
                                await bot.send_message(chat_id, msg, parse_mode="Markdown")
                            except Exception as e:
                                logger.error(f"Failed to send alert to {chat_id}: {e}")
                        alert_active["ram"] = True
                        last_alert_time["ram"] = current_time
            else:
                if spike_start_time["ram"] is not None:
                    logger.info(f"RAM usage went below threshold ({ram}% <= {RAM_THRESHOLD}%). Resetting delay timer.")
                spike_start_time["ram"] = None
                if alert_active["ram"]:
                    msg = f"✅ **RECOVERY: RAM** ✅\n\nMemory usage went back to normal: **{ram:.1f}%**"
                    for chat_id in ALLOWED_CHAT_IDS:
                        try:
                            await bot.send_message(chat_id, msg, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to send recovery to {chat_id}: {e}")
                    alert_active["ram"] = False

            # --- Check Disk ---
            disk = status["disk_percent"]
            if disk > DISK_THRESHOLD:
                if not alert_active["disk"] or (current_time - last_alert_time["disk"] > ALERT_COOLDOWN):
                    msg = (
                        f"🚨 **RESOURCE ALERT: DISK** 🚨\n\n"
                        f"⚠️ Disk space usage is at **{disk:.1f}%** (threshold: {DISK_THRESHOLD}%)\n"
                        f"Used: `{status['disk_used_gb']:.1f} GB` / Total: `{status['disk_total_gb']:.1f} GB`"
                    )
                    for chat_id in ALLOWED_CHAT_IDS:
                        try:
                            await bot.send_message(chat_id, msg, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to send alert to {chat_id}: {e}")
                    alert_active["disk"] = True
                    last_alert_time["disk"] = current_time
            else:
                if alert_active["disk"]:
                    msg = f"✅ **RECOVERY: DISK** ✅\n\nDisk space usage went back to normal: **{disk:.1f}%**"
                    for chat_id in ALLOWED_CHAT_IDS:
                        try:
                            await bot.send_message(chat_id, msg, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to send recovery to {chat_id}: {e}")
                    alert_active["disk"] = False

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = get_dispatcher(bot)
    
    # Send startup notification to all admins
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id, 
                "🚀 **VPS Monitoring Bot has started successfully!**\n"
                "Use `/start` or `/status` to view the control panel.",
                parse_mode="Markdown"
            )
            logger.info(f"Sent startup message to admin ID: {chat_id}")
        except Exception as e:
            logger.error(f"Could not send startup message to {chat_id}: {e}")
            
    logger.info("Starting Telegram Bot long-polling...")
    
    # Run the polling and the monitoring loop concurrently
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            monitoring_task(bot)
        )
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Monitoring application stopped.")
