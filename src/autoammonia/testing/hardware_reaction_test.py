from ..utils.redis_client import client
from ..config.config import DEFAULT_CONFIG

def main():
    """
    Main function to run hardware tests.
    This function will check the status of peristaltic pumps, syringe pumps, valves,
    and the spectrometer with lamp.
    """
    #Checking peristaltic pumps
    for pump in ['longerCE01', 'longerWE01']:
        try:
            from ..hardware.peristaltic_pumps import run_pump, stop_pump, check_pump
            run_pump(pump=pump, speed=1.0, direction=True)
            expected_status = float(client.get(str(pump)))
            actual_status = check_pump(pump=pump)
            if actual_status != 1.0:
                print(
                    f"Pump {pump} status mismatch: expected {expected_status}, got {actual_status}"
                )
            else:
                print(f"Pump {pump} is running as expected.")
            stop_pump(pump = pump)
        except Exception as e:
             print(f"Error checking peristaltic pump {pump}: {e}")
    
            
    #Checking syringe pumps
    for pump in ['tecanRX01',]:
        try:
            from ..hardware.syringe_pumps import syringe_draw, syringe_dispense
            syringe_draw(syringe_pump=pump, volume=0.05, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
            syringe_dispense(syringe_pump=pump, volume=0.05, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
            print(f"Syringe pump {pump} checked successfully.")
        except Exception as e:
            print(f"Error checking syringe pump {pump}: {e}")
    
    #Checking valves
    for valve in ['valveRX01',]:
        try:
            from ..hardware.selection_valves import switch_port_valve
            switch_port_valve(valve=valve, port="waste")
            print(f"Valve {valve} switched to port <waste> successfully.")
        except Exception as e:
            print(f"Error switching valve {valve}: {e}")