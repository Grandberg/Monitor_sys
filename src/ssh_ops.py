"""SSH remote operations for non-local servers (e.g. MYOR)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncssh

from src.config import ServerConfig

logger = logging.getLogger(__name__)

# Compact remote collector — uses host python3 + psutil (already on MYOR).
_REMOTE_STATUS_SCRIPT = r"""
import json, time, os
try:
    import psutil
except Exception as e:
    print(json.dumps({"error": f"psutil missing: {e}"}))
    raise SystemExit(0)

def cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for name in ("coretemp", "cpu_thermal", "k10temp", "zenpower"):
            if name in temps and temps[name]:
                return temps[name][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        return None
    return None

cpu = psutil.cpu_percent(interval=0.5)
mem = psutil.virtual_memory()
disk = psutil.disk_usage("/")
try:
    load = list(psutil.getloadavg())
except Exception:
    load = None
uptime = time.time() - psutil.boot_time()
print(json.dumps({
    "cpu_percent": cpu,
    "ram_percent": mem.percent,
    "ram_used_gb": mem.used / (1024 ** 3),
    "ram_total_gb": mem.total / (1024 ** 3),
    "disk_percent": disk.percent,
    "disk_used_gb": disk.used / (1024 ** 3),
    "disk_total_gb": disk.total / (1024 ** 3),
    "cpu_temp": cpu_temp(),
    "load_avg": load,
    "uptime": uptime,
}))
"""


async def _run_ssh(server: ServerConfig, command: str, timeout: float = 30.0) -> tuple[int, str, str]:
    if not server.host or not server.user or not server.key_path:
        return -2, "", "SSH server config incomplete (host/user/key_path)"

    try:
        async with asyncssh.connect(
            server.host,
            port=server.port,
            username=server.user,
            client_keys=[server.key_path],
            known_hosts=None,
            connect_timeout=15,
        ) as conn:
            result = await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)
            return int(result.exit_status or 0), (result.stdout or "").strip(), (result.stderr or "").strip()
    except asyncssh.Error as e:
        logger.error(f"SSH error to {server.id} ({server.host}): {e}")
        return -1, "", str(e)
    except Exception as e:
        logger.error(f"SSH failure to {server.id} ({server.host}): {e}")
        return -2, "", str(e)


async def get_system_status(server: ServerConfig) -> dict[str, Any]:
    code, stdout, stderr = await _run_ssh(
        server,
        f"python3 - <<'PY'\n{_REMOTE_STATUS_SCRIPT}\nPY",
        timeout=25.0,
    )
    if code != 0 or not stdout:
        raise RuntimeError(f"Remote status failed on {server.id}: {stderr or stdout or f'exit {code}'}")
    try:
        data = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from {server.id}: {stdout[:200]}") from e
    if "error" in data:
        raise RuntimeError(f"{server.id}: {data['error']}")
    return data


async def get_docker_status_info(server: ServerConfig) -> str:
    code, stdout, stderr = await _run_ssh(
        server,
        "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.RunningFor}}'",
        timeout=20.0,
    )
    if code != 0:
        return (
            f"Unable to fetch Docker status on **{server.name}**.\n"
            f"Error: {stderr or stdout or f'exit {code}'}"
        )
    if not stdout or len(stdout.strip().split("\n")) <= 1:
        return f"🐳 No active Docker containers on **{server.name}**."
    return f"🐳 **Running Containers ({server.name}):**\n\n```\n{stdout}\n```"


async def reboot_vps(server: ServerConfig) -> tuple[bool, str]:
    code, stdout, stderr = await _run_ssh(server, "sudo shutdown -r now", timeout=15.0)
    if code == 0 or code == -1 or "reboot" in (stderr + stdout).lower() or "shutdown" in (stderr + stdout).lower():
        return True, f"Reboot command sent to **{server.name}**. The server is restarting..."
    return False, f"Failed to reboot {server.name}. Error: {stderr or stdout}"


async def shutdown_vps(server: ServerConfig) -> tuple[bool, str]:
    code, stdout, stderr = await _run_ssh(server, "sudo shutdown -h now", timeout=15.0)
    if code == 0 or code == -1 or "shutdown" in (stderr + stdout).lower() or "poweroff" in (stderr + stdout).lower():
        return True, f"Shutdown command sent to **{server.name}**. The server is shutting down..."
    return False, f"Failed to shutdown {server.name}. Error: {stderr or stdout}"


async def restart_docker(server: ServerConfig) -> tuple[bool, str]:
    code, stdout, stderr = await _run_ssh(server, "sudo systemctl restart docker", timeout=60.0)
    if code == 0 or code == -1:
        return True, f"Docker restart command sent on **{server.name}**."
    return False, f"Failed to restart Docker on {server.name}. Error: {stderr or stdout}"
