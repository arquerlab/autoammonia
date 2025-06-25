from ..utils.redis_client import client
from ..config.config import DEFAULT_CONFIG

def main():
    """
    Main function to run hardware tests.
    This function will check the status of peristaltic pumps, syringe pumps, valves,
    and the spectrometer with lamp.
    """
    # Checking syringe pumps
    for pump in ['tecanAZ01',]:
        try:
            from ..hardware.syringe_pumps import syringe_draw, syringe_dispense
            syringe_draw(syringe_pump=pump, volume=0.05, valve_port='waste', speed=DEFAULT_CONFIG['syringe_wash_speed'])
            syringe_dispense(syringe_pump=pump, volume=0.05, valve_port='waste',
                             speed=DEFAULT_CONFIG['syringe_wash_speed'])
            print(f"Syringe pump {pump} checked successfully.")
        except Exception as e:
            print(f"Error checking syringe pump {pump}: {e}")

    # Checking valves
    for valve in ['valveAZ01',]:
        try:
            from ..hardware.selection_valves import switch_port_valve
            switch_port_valve(valve=valve, port="waste")
            print(f"Valve {valve} switched to port <waste> successfully.")
        except Exception as e:
            print(f"Error switching valve {valve}: {e}")
    #checking spectrometer and lamp
    try:
        from ..hardware.uv_vis_module import lamp_switch, acquire_spectrum
        lamp_switch(lamp='lamp01', on=True)
        acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time=1.0)
        lamp_switch(lamp='lamp01', on=False)
        print("Spectrometer and lamp checked successfully.")
    except Exception as e:
        print(f"Error checking spectrometer or lamp: {e}")

