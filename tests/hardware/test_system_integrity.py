"""
System integrity test for hardware and service components.

Runs a quick check-in sequence for every hardware component and core service
to verify that everything is connected and responsive, using the existing
unit-op helpers without duplicating their logic.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable, Dict, List, Tuple

import pytest

from . import unit_op_hardware as hw
from . import unit_op_services as svc


HardwareFn = Callable[..., Tuple[str, str, Any]]
ServiceFn = Callable[[], Tuple[str, str, Any]]


HARDWARE_CHECKS: List[Tuple[str, HardwareFn, List[str]]] = [
    ("peristaltic_pump", hw.peristaltic_pump_unit_op, ["longerCE01", "longerWE01"]),
    ("syringe_pump", partial(hw.syringe_pump_unit_op, volume=0.05), ["tecanRX01"]),
    ("valve", partial(hw.valve_unit_op, port="waste"), ["valveRX01"]),
    ("lamp", hw.lamp_unit_op, ["lamp01"]),
    ("potentiostat", hw.potentiostat_unit_op, ["potentiostat01"]),
    ("uv_vis", lambda name: hw.uv_vis_unit_op(spec=name), ["UVVIS01"]),
]

SERVICE_CHECKS: List[Tuple[str, ServiceFn]] = [
    ("redis", svc.redis_unit_op),
    ("db", svc.db_unit_op),
    ("queue", svc.queue_unit_op),
]


@pytest.mark.hardware
def test_system_integrity(hardware_summary: List[Dict[str, str]]) -> None:
    """
    Run a single, aggregated integrity check for hardware and services.
    """
    results: List[Dict[str, str]] = []

    # Hardware checks: iterate over a small configuration table
    for kind, func, names in HARDWARE_CHECKS:
        for name in names:
            comp_name, status, info = func(name)
            results.append(
                {
                    "kind": kind,
                    "name": comp_name,
                    "status": status,
                    "error": str(info),
                }
            )

    # Service checks
    for kind, tester in SERVICE_CHECKS:
        name, status, info = tester()
        results.append(
            {
                "kind": kind,
                "name": name,
                "status": status,
                "error": str(info),
            }
        )

    # Prefect (async) – kept separate because it is awaitable
    name, status, info = asyncio.run(svc.prefect_unit_op())
    results.append(
        {
            "kind": "prefect",
            "name": name,
            "status": status,
            "error": str(info),
        }
    )

    hardware_summary.extend(results)

    failures = [r for r in results if r.get("status") != "OK"]
    if failures:
        lines = [
            f"{r['kind']} '{r['name']}': {r['status']} ({r['error']})"
            for r in failures
        ]
        pytest.fail("System integrity check failed:\n" + "\n".join(lines))

