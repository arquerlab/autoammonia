"""
Unit operation tests for hardware.
"""
from typing import Tuple, Optional
from autoammonia.hardware.peristaltic_pumps import run_pump, stop_pump, check_pump
from autoammonia.hardware.syringe_pumps import syringe_draw, syringe_dispense
from autoammonia.hardware.selection_valves import switch_port_valve
from autoammonia.hardware.uv_vis_module import spec_acquire, lamp_switch
from autoammonia.hardware.potentiostat import run_method_parallel
from autoammonia.config.config import DEFAULT_CONFIG
from autoammonia.config.components_config import CONFIG_COMPONENTS


def peristaltic_pump_unit_op(pump_name: str) -> Tuple[str, str, Optional[float]]:
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


def syringe_pump_unit_op(pump_name: str, volume: float = 0.05) -> Tuple[str, str, Optional[str]]:
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


def valve_unit_op(valve_name: str, port: str = "waste") -> Tuple[str, str, Optional[str]]:
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


def uv_vis_unit_op(spec: str = "UVVIS01", 
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
        spectrum = spec_acquire(
            spectrometer=spec,
            integration_time=integration_time,
            retries=3
        )
        return ("OK", spectrum, None)
    except Exception as e:
        return ("FAILED", None, str(e))

def lamp_unit_op(lamp: str = "lamp01") -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on a lamp.
    
    Args:
        lamp: Name of the lamp to test.
    
    Returns:
        Tuple of (lamp_name, status, error_message) where status is "OK" or "FAILED".
    """
    try:
        lamp_switch(lamp=lamp, on=True)
        lamp_switch(lamp=lamp, on=False)
        return (lamp, "OK", None)
    except Exception as e:
        return (lamp, "FAILED", str(e))


def potentiostat_unit_op(potentiostat: str = "potentiostat01") -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on a potentiostat.
    
    Args:
        potentiostat: Name of the potentiostat to test.
    
    Returns:
        Tuple of (potentiostat_name, status, error_message) where status is "OK" or "FAILED".
    """
    try:
        #Count number of potentiostats available
        count_potentiostats = lambda elems: sum(1 for elem in elems if "potentiostat" in elem)
        parallel_cells = count_potentiostats(CONFIG_COMPONENTS.keys())
        run_method_parallel(parallel_cells=parallel_cells,  folder='/tmp', experiment_ids=[i for i in range(1, parallel_cells + 1)],
        mode='CA', params={'potential': 0.0, 'duration': 1.0}, tia_gain=0, reducing_factor=None)
        return (potentiostat, "OK", None)
    except Exception as e:
        return (potentiostat, "FAILED", str(e))