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
    #Checking peristaltic pumps
    for pump in ['longerCE01', 'longerWE01']:
        try:
            run_pump(pump=pump, speed=1.0, direction=True)
            expected_status = float(client.get(pump))
            actual_status = check_pump(pump=pump)
            if actual_status != expected_status:
                print(
                    f"Pump {pump} status mismatch: expected {expected_status}, got {actual_status}"
                )
            else:
                print(f"Pump {pump} is running as expected.")
        finally:
            stop_pump(pump=pump)
    
            
    #Checking syringe pumps
    for pump in ['tecanAZ01', 'tecanRX01']:
        try:
            syringe_draw(syringe_pump=pump, volume=0.05, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
            syringe_dispense(syringe_pump=pump, volume=0.25, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
            print(f"Syringe pump {pump} checked successfully.")
        except Exception as e:
            print(f"Error checking syringe pump {pump}: {e}")
    
    #Checking valves
    for valve in ['valveRX01', 'valveAZ01']:
        try:
            switch_port_valve(valve=valve, port=2)
            switch_port_valve(valve=valve, port=1)
            print(f"Valve {valve} switched to port 2 and back to port 1 successfully.")
        except Exception as e:
            print(f"Error switching valve {valve}: {e}")
        
    #checking spectrometer and lamp
    try:
        lamp_switch(lamp='lamp01', on=True)
        acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time=1.0)
        lamp_switch(lamp='lamp01', on=False)
        print("Spectrometer and lamp checked successfully.")
    except Exception as e:
        print(f"Error checking spectrometer or lamp: {e}")

        