"""
Minimal pytest-style hardware smoke tests using unit operation helpers.

These tests are marked as hardware tests and rely on real hardware being
connected and correctly configured. Run them explicitly, e.g.:

    pytest tests/hardware/test_hardware.py -m hardware
"""

import pytest

from .unit_op_hardware import (
    peristaltic_pump_unit_op,
    syringe_pump_unit_op,
    valve_unit_op,
    lamp_unit_op,
    potentiostat_unit_op,
    uv_vis_unit_op,
)


@pytest.mark.hardware
@pytest.mark.parametrize("pump_name", ["longerWE01", "longerCE01"])
def test_peristaltic_pumps_basic(pump_name: str, hardware_summary) -> None:
    """
    Basic peristaltic pump check using the unit-op helper.
    """
    name, status, status_value = peristaltic_pump_unit_op(pump_name)
    hardware_summary.append(
        {
            "kind": "peristaltic_pump",
            "name": name,
            "status": status,
            "error": status_value,
        }
    )
    print(f"Peristaltic pump test result: {name}, {status}, {status_value}")
    assert status == "OK", f"Peristaltic pump {name} test failed: {status_value}"


@pytest.mark.hardware
@pytest.mark.parametrize("pump_name", ["tecanRX01", "tecanAZ01"])
def test_syringe_pump_basic(pump_name: str, hardware_summary) -> None:
    """
    Basic syringe pump check using the unit-op helper.
    """
    name, status, error = syringe_pump_unit_op(pump_name, volume=0.05)
    hardware_summary.append(
        {
            "kind": "syringe_pump",
            "name": name,
            "status": status,
            "error": error,
        }
    )
    print(f"Syringe pump test result: {name}, {status}, {error}")
    assert status == "OK", f"Syringe pump {name} test failed: {error}"


@pytest.mark.hardware
@pytest.mark.parametrize("valve_name", ["valveRX01", "valveAZ01"])
def test_valve_basic(valve_name: str, hardware_summary) -> None:
    """
    Basic valve check using the unit-op helper.
    """
    name, status, error = valve_unit_op(valve_name, port="waste")
    hardware_summary.append(
        {
            "kind": "valve",
            "name": name,
            "status": status,
            "error": error,
        }
    )
    print(f"Valve test result: {name}, {status}, {error}")
    assert status == "OK", f"Valve {name} test failed: {error}"


@pytest.mark.hardware
@pytest.mark.parametrize("lamp_name", ["lamp01"])
def test_lamp_basic(lamp_name: str, hardware_summary) -> None:
    """
    Basic lamp check using the unit-op helper.
    """
    name, status, error = lamp_unit_op(lamp_name)
    hardware_summary.append(
        {
            "kind": "lamp",
            "name": name,
            "status": status,
            "error": error,
        }
    )
    print(f"Lamp test result: {name}, {status}, {error}")
    assert status == "OK", f"Lamp {name} test failed: {error}"


@pytest.mark.hardware
@pytest.mark.parametrize("potentiostat_name", ["potentiostat01"])
def test_potentiostat_basic(potentiostat_name: str, hardware_summary) -> None:
    """
    Basic potentiostat check using the unit-op helper.
    """
    name, status, error = potentiostat_unit_op(potentiostat_name)
    hardware_summary.append(
        {
            "kind": "potentiostat",
            "name": name,
            "status": status,
            "error": error,
        }
    )
    print(f"Potentiostat test result: {name}, {status}, {error}")
    assert status == "OK", f"Potentiostat {name} test failed: {error}"


@pytest.mark.hardware
@pytest.mark.parametrize("spec_name", ["UVVIS01"])
def test_uv_vis_basic(spec_name: str, hardware_summary) -> None:
    """
    Basic UV-Vis spectrometer check using the unit-op helper.
    """
    status, spectrum, error = uv_vis_unit_op(spec=spec_name, integration_time=1.0)
    hardware_summary.append(
        {
            "kind": "uv_vis",
            "name": spec_name,
            "status": status,
            "error": error,
        }
    )
    print(f"UV-Vis test result: {status}, {spectrum}, {error}")
    assert status == "OK", f"UV-Vis {spec_name} test failed: {error}"