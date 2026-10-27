"""Intentionally restricted Modbus TCP client: read registers only (FC03/FC04).

Plaintext Modbus TCP has no authentication or confidentiality. Not production-ready.
Connection is OFF by default and restricted to loopback unless explicitly authorized.
No write function is implemented.
"""
from __future__ import annotations

import ipaddress
import socket
import struct


class ModbusError(Exception):
    pass


def _exact(sock: socket.socket, size: int) -> bytes:
    if size < 0 or size > 260:
        raise ModbusError("Invalid response length")
    data = bytearray()
    while len(data) < size:
        received = sock.recv(size - len(data))
        if not received:
            raise ModbusError("Connection closed before full response")
        data.extend(received)
    return bytes(data)


def read_registers(host: str, port: int, address: int, count: int, *, unit_id: int = 1,
                   kind: str = "holding", enable_network: bool = False,
                   allow_remote: bool = False, authorized: bool = False,
                   timeout: float = 2.0) -> list[int]:
    """Read only. For remote devices set three authorization switches intentionally.

    This is a laboratory diagnostic; use a secured OT gateway for real deployments.
    """
    if not enable_network:
        raise PermissionError("Network disabled by default; explicit enable_network required")
    if kind not in ("holding", "input"):
        raise ValueError("Only read holding/input registers supported")
    if any(type(x) is not int for x in (port, address, count, unit_id)):
        raise ValueError("Port/address/count/unit must be integers")
    if not 1 <= port <= 65535 or not 0 <= address <= 65535 or not 1 <= count <= 125 or address + count > 65536 or not 0 <= unit_id <= 247:
        raise ValueError("Invalid Modbus range")
    if not 0.05 <= timeout <= 10:
        raise ValueError("Timeout must be 0.05..10 seconds")
    if not host or len(host) > 253:
        raise ValueError("Invalid host")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ModbusError(f"DNS resolution failed: {exc}") from exc
    if not addresses:
        raise ModbusError("No host addresses returned")
    # Pin connection to one resolved numeric IP; do not resolve hostname again.
    allowed = []
    for family, socktype, proto, canon, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback:
            allowed.append((family, socktype, proto, sockaddr))
        elif allow_remote and authorized:
            allowed.append((family, socktype, proto, sockaddr))
    if not allowed:
        raise PermissionError("Remote connections require allow_remote AND authorized; use an approved OT gateway")
    family, socktype, proto, sockaddr = allowed[0]
    function = 3 if kind == "holding" else 4
    transaction = 0x712C
    request = struct.pack(">HHHBBHH", transaction, 0, 6, unit_id, function, address, count)
    try:
        with socket.socket(family, socktype, proto) as sock:
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            sock.sendall(request)
            mbap = _exact(sock, 7)
            tx, protocol, length, response_unit = struct.unpack(">HHHB", mbap)
            if tx != transaction or protocol != 0 or response_unit != unit_id:
                raise ModbusError("Mismatched Modbus response header")
            if not 3 <= length <= 253:  # includes unit id and PDU
                raise ModbusError("Invalid Modbus response length")
            payload = _exact(sock, length - 1)
    except OSError as exc:
        raise ModbusError(f"Network operation failed: {exc}") from exc
    if payload[0] == (function | 0x80):
        if len(payload) != 2:
            raise ModbusError("Malformed Modbus exception")
        raise ModbusError(f"Modbus exception code {payload[1]}")
    if payload[0] != function or len(payload) < 2 or payload[1] != count * 2 or len(payload) != 2 + count * 2:
        raise ModbusError("Malformed or mismatched Modbus payload")
    return list(struct.unpack(">" + "H" * count, payload[2:]))
