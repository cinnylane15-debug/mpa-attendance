import asyncio
import socket

import psutil
from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from models import ListeningPort, NetworkInterface, PortCheckRequest, MessageResponse
from utils.shell import run_command

router = APIRouter(prefix="/network", tags=["Network"])


@router.get("/interfaces", response_model=list[NetworkInterface])
async def network_interfaces(user: dict = Depends(get_current_user)):
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    result = []

    for iface, addr_list in addrs.items():
        ipv4 = []
        ipv6 = []
        mac = ""
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ipv4.append(addr.address)
            elif addr.family == socket.AF_INET6:
                ipv6.append(addr.address)
            elif addr.family == psutil.AF_LINK:
                mac = addr.address

        stat = stats.get(iface)
        status = "up" if stat and stat.isup else "down"

        result.append(NetworkInterface(
            name=iface,
            ipv4=ipv4,
            ipv6=ipv6,
            mac=mac,
            status=status,
        ))

    return result


@router.get("/ports", response_model=list[ListeningPort])
async def listening_ports(user: dict = Depends(get_current_user)):
    connections = psutil.net_connections(kind="inet")
    result = []
    seen = set()

    for conn in connections:
        if conn.status != "LISTEN":
            continue
        key = (conn.laddr.ip, conn.laddr.port)
        if key in seen:
            continue
        seen.add(key)

        process_name = ""
        pid = conn.pid
        if pid:
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        result.append(ListeningPort(
            protocol="tcp",
            local_address=conn.laddr.ip,
            port=conn.laddr.port,
            pid=pid,
            process=process_name,
        ))

    result.sort(key=lambda p: p.port)
    return result


@router.get("/check-port")
async def check_port(
    host: str = Query(...),
    port: int = Query(..., ge=1, le=65535),
    user: dict = Depends(get_current_user),
):
    """Check if a remote port is reachable."""
    loop = asyncio.get_event_loop()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return {"host": host, "port": port, "reachable": True}
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return {"host": host, "port": port, "reachable": False}


@router.get("/firewall")
async def firewall_status(user: dict = Depends(get_current_user)):
    result = await run_command("ufw status verbose 2>/dev/null || echo 'ufw not installed'")
    return {"output": result.stdout or result.stderr, "success": result.success}
