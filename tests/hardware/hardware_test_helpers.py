"""
Helper functions for hardware testing.

Contains reusable test logic that can be shared between unit tests
and system integrity tests.
"""
from typing import Tuple, Optional
from autoammonia.hardware.peristaltic_pumps import run_pump, stop_pump, check_pump
from autoammonia.hardware.syringe_pumps import syringe_draw, syringe_dispense
from autoammonia.hardware.selection_valves import switch_port_valve
from autoammonia.hardware.uv_vis_module import acquire_spectrum
from autoammonia.config.config import DEFAULT_CONFIG


def test_peristaltic_pump_basic(pump_name: str) -> Tuple[str, str, Optional[float]]:
    """
    Run a basic test on a peristaltic pump.
    
    Args:
        pump_name: Name of the pump to test.
    
    Returns:
        Tuple of (pump_name, status, status_value) where status is "OK" or "FAILED".
    """
    try:
        run_pump(pump=pump_name, speed=1.0, direction=True)
        status = check_pump(pump=pump_name)
        stop_pump(pump=pump_name)
        return (pump_name, "OK", status)
    except Exception as e:
        return (pump_name, "FAILED", str(e))


def test_syringe_pump_basic(pump_name: str, volume: float = 0.05) -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on a syringe pump.
    
    Args:
        pump_name: Name of the pump to test.
        volume: Volume to draw and dispense (in mL).
    
    Returns:
        Tuple of (pump_name, status, error_message) where status is "OK" or "FAILED".
    """
    try:
        test_speed = DEFAULT_CONFIG['syringe_wash_speed']
        syringe_draw(
            syringe_pump=pump_name,
            volume=volume,
            valve_port='waste',
            speed=test_speed
        )
        syringe_dispense(
            syringe_pump=pump_name,
            volume=volume,
            valve_port='waste',
            speed=test_speed
        )
        return (pump_name, "OK", None)
    except Exception as e:
        return (pump_name, "FAILED", str(e))


def test_valve_basic(valve_name: str, port: str = "waste") -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on a selection valve.
    
    Args:
        valve_name: Name of the valve to test.
        port: Port to switch to.
    
    Returns:
        Tuple of (valve_name, status, error_message) where status is "OK" or "FAILED".
    """
    try:
        switch_port_valve(valve=valve_name, port=port)
        return (valve_name, "OK", None)
    except Exception as e:
        return (valve_name, "FAILED", str(e))


def test_uv_vis_basic(spectrometer: str = "UVVIS01", lamp: str = "lamp01", 
                      integration_time: float = 1.0) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Run a basic test on UV-Vis spectrometer and lamp.
    
    Args:
        spectrometer: Name of the spectrometer.
        lamp: Name of the lamp.
        integration_time: Integration time for spectrum acquisition.
    
    Returns:
        Tuple of (status, spectrum_length, error_message) where status is "OK" or "FAILED".
    """
    try:
        spectrum = acquire_spectrum(
            spectrometer=spectrometer,
            lamp=lamp,
            integration_time=integration_time
        )
        return ("OK", len(spectrum), None)
    except Exception as e:
        return ("FAILED", None, str(e))

