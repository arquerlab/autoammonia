from prefect import get_run_logger

from ..config.config import DEFAULT_CONFIG
from ..hardware.peristaltic_pumps import run_pump, stop_pump, check_pump
from ..hardware.selection_valves import switch_port_valve
from ..utils.redis_client import client
from ..hardware.syringe_pumps import syringe_draw, syringe_dispense
from ..hardware.uv_vis_module import lamp_switch, acquire_spectrum

def main():
    """
    Main function to run hardware tests.
    This function will check the status of peristaltic pumps, syringe pumps, valves,
    and the spectrometer with lamp.
    """
    logger = get_run_logger()
    #Checking peristaltic pumps
    for pump in ['longerCE01', 'longerWE01']:
        try:
            run_pump(pump=pump, speed=1.0, direction=True)
            expected_status = float(client.get(pump))
            actual_status = check_pump(pump=pump)
            if actual_status != expected_status:
                raise RuntimeError(
                    f"Pump {pump} status mismatch: expected {expected_status}, got {actual_status}"
                )
            logger.info(f"Pump {pump} is running as expected.")
        finally:
            stop_pump(pump=pump)
    
            
    #Checking syringe pumps
    for pump in ['tecanAZ01', 'tecanRX01']:
        syringe_draw(syringe_pump=pump, volume=0.05, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
        syringe_dispense(syringe_pump=pump, volume=0.25, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
        logger.info(f"Syringe pump {pump} checked successfully.")
    
    #Checking valves
    for valve in ['valveRX01', 'valveAZ01']:
        switch_port_valve(valve=valve, port=2)
        switch_port_valve(valve=valve, port=1)
        logger.info(f"Valve {valve} switched to port 2 and back to port 1 successfully.")
        
    #checking spectrometer and lamp
    lamp_switch(lamp='lamp01', on=True)
    acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time=1.0)
    lamp_switch(lamp='lamp01', on=False)
    logger.info("Spectrometer and lamp checked successfully.")

        