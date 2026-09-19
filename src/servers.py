"""Route monitoring/control operations to local or SSH backends."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.config import SERVERS, SERVERS_BY_ID, ServerConfig
import src.monitor as monitor
import src.utils as utils
import src.ssh_ops as ssh_ops

logger = logging.getLogger(__name__)


def list_servers() -> list[ServerConfig]:
    return list(SERVERS)


def get_server(server_id: str) -> ServerConfig | None:
    return SERVERS_BY_ID.get(server_id)


async def get_system_status(server_id: str) -> dict[str, Any]:
    server = get_server(server_id)
    if not server:
        raise ValueError(f"Unknown server: {server_id}")
    if server.type == "local":
        return await asyncio.to_thread(monitor.get_system_status)
    if server.type == "ssh":
        return await ssh_ops.get_system_status(server)
    raise ValueError(f"Unsupported server type: {server.type}")


async def get_docker_status_info(server_id: str) -> str:
    server = get_server(server_id)
    if not server:
        return f"Unknown server: {server_id}"
    if server.type == "local":
        return await asyncio.to_thread(utils.get_docker_status_info)
    if server.type == "ssh":
        return await ssh_ops.get_docker_status_info(server)
    return f"Unsupported server type: {server.type}"


async def reboot_vps(server_id: str) -> tuple[bool, str]:
    server = get_server(server_id)
    if not server:
        return False, f"Unknown server: {server_id}"
    if server.type == "local":
        return await asyncio.to_thread(utils.reboot_vps)
    if server.type == "ssh":
        return await ssh_ops.reboot_vps(server)
    return False, f"Unsupported server type: {server.type}"


async def shutdown_vps(server_id: str) -> tuple[bool, str]:
    server = get_server(server_id)
    if not server:
        return False, f"Unknown server: {server_id}"
    if server.type == "local":
        return await asyncio.to_thread(utils.shutdown_vps)
    if server.type == "ssh":
        return await ssh_ops.shutdown_vps(server)
    return False, f"Unsupported server type: {server.type}"


async def restart_docker(server_id: str) -> tuple[bool, str]:
    server = get_server(server_id)
    if not server:
        return False, f"Unknown server: {server_id}"
    if server.type == "local":
        return await asyncio.to_thread(utils.restart_docker)
    if server.type == "ssh":
        return await ssh_ops.restart_docker(server)
    return False, f"Unsupported server type: {server.type}"
