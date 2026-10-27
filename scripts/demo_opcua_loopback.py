#!/usr/bin/env python3
"""Disposable 127.0.0.1 OPC UA server -> explicitly enabled read-only client.

Requires opt-in: pip install '.[industrial-opcua]'. No remote PLC access.
"""
from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trinitylab.industrial.opcua import (load_opcua_profile,
                                        opcua_profile_drift,
                                        read_opcua_snapshot)


def ephemeral_loopback_port() -> int:
    # Port is released before server binds. Works for controlled local tests.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def run_demo() -> dict:
    from asyncua import Server, ua

    profile = load_opcua_profile(ROOT / "fixtures/industrial/opcua_profile_v1.json")
    future = load_opcua_profile(ROOT / "fixtures/industrial/opcua_profile_v2.json")
    port = ephemeral_loopback_port()
    endpoint = f"opc.tcp://127.0.0.1:{port}/trinity/lab/"
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("TRINITY local-only test fixture")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    namespace_index = await server.register_namespace(profile.namespace_uri)
    obj = await server.nodes.objects.add_object(namespace_index, "Pump")
    for identifier, value in (("MotorTemperature", 42.0), ("ShaftSpeed", 1800.0),
                              ("LinePressure", 1234.0)):
        # Deliberately no set_writable(); server is a disposable read-only fixture.
        await obj.add_variable(ua.NodeId(identifier, namespace_index), identifier, value)
    async with server:
        first = await read_opcua_snapshot(profile, endpoint, enable_network=True)
        second = await read_opcua_snapshot(profile, endpoint, enable_network=True)
    assert [x["quality"] for x in first["signals"]] == ["good", "good", "good"]
    assert abs(first["signals"][2]["value"] - 12.34) < 1e-8
    assert [x["value"] for x in first["signals"]] == [x["value"] for x in second["signals"]]
    result = {"project": "trinity_industrial", "scenario": "local_opcua_read_only",
              "endpoint": "127.0.0.1 (ephemeral port)", "snapshot": first,
              "fresh_session_again": True, "profile_drift": opcua_profile_drift(profile, future),
              "caveat": "Disposable local server, no encryption, production PLC, or safety certification"}
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(run_demo()), indent=2))
    except ImportError:
        raise SystemExit('Install optional extras first: pip install ".[industrial-opcua]"')
