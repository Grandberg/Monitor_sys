import os
import subprocess
import logging
from src.config import HOST_ROOT_PATH

logger = logging.getLogger(__name__)

# Commands from environment variables or defaults
CMD_REBOOT = os.getenv("CMD_REBOOT", "shutdown -r now")
CMD_SHUTDOWN = os.getenv("CMD_SHUTDOWN", "shutdown -h now")
CMD_RESTART_DOCKER = os.getenv("CMD_RESTART_DOCKER", "systemctl restart docker")

def run_host_command(cmd: str) -> tuple[int, str, str]:
    """Runs a command on the host filesystem via chroot."""
    # Check if we are running inside Docker and the host root filesystem is mounted
    if os.path.exists(HOST_ROOT_PATH) and os.path.isdir(HOST_ROOT_PATH):
        # We run the command via chroot to access the host's executables and systemd
        full_cmd = ["chroot", HOST_ROOT_PATH, "bash", "-c", cmd]
    else:
        # Fallback to direct execution for local testing
        full_cmd = ["bash", "-c", cmd]
        
    try:
        logger.info(f"Executing host command: {cmd}")
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {cmd}")
        return -1, "", "Command timed out after 15 seconds"
    except Exception as e:
        logger.error(f"Error running command '{cmd}': {str(e)}")
        return -2, "", str(e)

def reboot_vps() -> tuple[bool, str]:
    """Triggers a VPS reboot."""
    code, stdout, stderr = run_host_command(CMD_REBOOT)
    # Reboot will terminate the system, so if it succeeds, we might not get a response,
    # or we might get a connection error. This is expected.
    if code == 0 or "reboot" in stderr.lower() or "shutdown" in stderr.lower() or code == -1:
        return True, "Reboot command sent successfully. The server is restarting..."
    return False, f"Failed to reboot VPS. Error: {stderr or stdout}"

def shutdown_vps() -> tuple[bool, str]:
    """Triggers a VPS shutdown."""
    code, stdout, stderr = run_host_command(CMD_SHUTDOWN)
    if code == 0 or "shutdown" in stderr.lower() or "poweroff" in stderr.lower() or code == -1:
        return True, "Shutdown command sent successfully. The server is shutting down..."
    return False, f"Failed to shutdown VPS. Error: {stderr or stdout}"

def restart_docker() -> tuple[bool, str]:
    """Restarts the Docker service on the host."""
    code, stdout, stderr = run_host_command(CMD_RESTART_DOCKER)
    # Note: restarting docker will terminate this container. If docker service starts successfully,
    # the container will restart if configured with restart: always.
    if code == 0 or code == -1: # -1 might be timeout as docker stops containers
        return True, "Docker service restart command sent. This container will restart."
    return False, f"Failed to restart Docker. Error: {stderr or stdout}"

def get_docker_status_info() -> str:
    """Gets status information about docker containers running on the host."""
    # Try running 'docker ps' via chroot
    code, stdout, stderr = run_host_command("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'")
    if code != 0:
        return f"Unable to fetch Docker status. Docker CLI not available on host or failed.\nError: {stderr or stdout}"
    
    if not stdout or len(stdout.strip().split("\n")) <= 1:
        return "🐳 No active Docker containers running on the host."
        
    # Format the docker ps output
    return f"🐳 **Running Containers:**\n\n```\n{stdout}\n```"
