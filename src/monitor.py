import psutil
import time
import os
from src.config import HOST_ROOT_PATH

def get_cpu_usage() -> float:
    """Returns the current CPU usage percentage."""
    # interval=None is non-blocking, but can return 0 on first call. 
    # We'll use 0.5 or 1 second when called on demand, or non-blocking in loops.
    return psutil.cpu_percent(interval=0.5)

def get_ram_usage():
    """Returns (percent, used_bytes, total_bytes)."""
    mem = psutil.virtual_memory()
    return mem.percent, mem.used, mem.total

def get_disk_usage():
    """Returns (percent, used_bytes, total_bytes) of the host system."""
    # Check if the host root path exists, otherwise fallback to container root
    path = HOST_ROOT_PATH if os.path.exists(HOST_ROOT_PATH) else "/"
    disk = psutil.disk_usage(path)
    return disk.percent, disk.used, disk.total

def get_cpu_temperature() -> float:
    """Returns the CPU temperature in Celsius if available, else None."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Look for standard CPU temp sensors
        for name in ['coretemp', 'cpu_thermal', 'k10temp', 'zenpower']:
            if name in temps and temps[name]:
                return temps[name][0].current
        # Fallback to any sensor
        for name, entries in temps.items():
            if entries:
                return entries[0].current
    except Exception:
        pass
    return None

def get_load_average():
    """Returns 1, 5, and 15 minute load averages."""
    try:
        # psutil.getloadavg() returns a tuple of 3 floats
        return psutil.getloadavg()
    except Exception:
        return None

def get_uptime_seconds() -> float:
    """Returns system uptime in seconds."""
    try:
        return time.time() - psutil.boot_time()
    except Exception:
        return 0.0

def get_system_status() -> dict:
    """Gathers all monitoring metrics into a single dictionary."""
    cpu = get_cpu_usage()
    ram_pct, ram_used, ram_total = get_ram_usage()
    disk_pct, disk_used, disk_total = get_disk_usage()
    temp = get_cpu_temperature()
    load = get_load_average()
    uptime = get_uptime_seconds()

    return {
        "cpu_percent": cpu,
        "ram_percent": ram_pct,
        "ram_used_gb": ram_used / (1024 ** 3),
        "ram_total_gb": ram_total / (1024 ** 3),
        "disk_percent": disk_pct,
        "disk_used_gb": disk_used / (1024 ** 3),
        "disk_total_gb": disk_total / (1024 ** 3),
        "cpu_temp": temp,
        "load_avg": load,
        "uptime": uptime
    }

def format_uptime(seconds: float) -> str:
    """Formats uptime seconds into a human-readable string."""
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
        
    return " ".join(parts)
