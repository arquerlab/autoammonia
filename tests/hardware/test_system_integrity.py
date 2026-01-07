"""
System integrity test for all hardware components.

Runs a quick check-in sequence for every configured hardware component.
This test verifies that all hardware is connected and responsive.

This test uses the same helper functions as the unit tests, but provides
a single summary view of all components.
"""
import pytest

from autoammonia.config.config import CONFIG_SETUP
from .hardware_test_helpers import (
    test_peristaltic_pump_basic,
    test_syringe_pump_basic,
    test_valve_basic,
    test_uv_vis_basic,
)


@pytest.mark.hardware
def test_all_hardware_components(hardware_test_mode, mock_redis):
    """
    Test all configured hardware components in sequence.
    
    This test runs a minimal operation on each component type to verify
    they are all connected and responsive. It uses the same helper functions
    as the unit tests, ensuring consistency.
    """
    results = {
        "peristaltic_pumps": [],
        "syringe_pumps": [],
        "valves": [],
        "uv_vis": None,
    }
    
    # Test peristaltic pumps
    for pump_name in ["longerWE01", "longerCE01"]:
        if pump_name in CONFIG_SETUP:
            result = test_peristaltic_pump_basic(pump_name)
            results["peristaltic_pumps"].append(result)
    
    # Test syringe pumps
    for pump_name in ["tecanRX01", "tecanAZ01"]:
        if pump_name in CONFIG_SETUP:
            result = test_syringe_pump_basic(pump_name)
            results["syringe_pumps"].append(result)
    
    # Test valves
    for valve_name in ["valveRX01", "valveAZ01"]:
        if valve_name in CONFIG_SETUP:
            result = test_valve_basic(valve_name)
            results["valves"].append(result)
    
    # Test UV-Vis
    if "lamp01" in CONFIG_SETUP and "UVVIS01" in CONFIG_SETUP:
        result = test_uv_vis_basic()
        results["uv_vis"] = result
    
    # Print results summary
    print("\n=== Hardware Test Results ===")
    print(f"Peristaltic Pumps: {results['peristaltic_pumps']}")
    print(f"Syringe Pumps: {results['syringe_pumps']}")
    print(f"Valves: {results['valves']}")
    print(f"UV-Vis: {results['uv_vis']}")
    
    # Collect failures
    failures = []
    for pump_name, status, *rest in results["peristaltic_pumps"]:
        if status == "FAILED":
            error_msg = rest[0] if rest else "Unknown error"
            failures.append(f"{pump_name}: {error_msg}")
    
    for pump_name, status, *rest in results["syringe_pumps"]:
        if status == "FAILED":
            error_msg = rest[0] if rest else "Unknown error"
            failures.append(f"{pump_name}: {error_msg}")
    
    for valve_name, status, *rest in results["valves"]:
        if status == "FAILED":
            error_msg = rest[0] if rest else "Unknown error"
            failures.append(f"{valve_name}: {error_msg}")
    
    if results["uv_vis"] and results["uv_vis"][0] == "FAILED":
        error_msg = results["uv_vis"][2] if len(results["uv_vis"]) > 2 else "Unknown error"
        failures.append(f"UV-Vis: {error_msg}")
    
    # Assert that all tests passed
    if failures:
        pytest.fail(f"Hardware test failures:\n" + "\n".join(failures))
    
    assert True, "All hardware components tested successfully"

