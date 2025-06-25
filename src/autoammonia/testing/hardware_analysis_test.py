from ..utils.redis_client import client
from ..config.config import DEFAULT_CONFIG

def main():
    """
    Main function to run hardware tests.
    This function will check the status of peristaltic pumps, syringe pumps, valves,
    and the spectrometer with lamp.
    """
    #checking spectrometer and lamp
    try:
        from ..hardware.uv_vis_module import lamp_switch, acquire_spectrum
        lamp_switch(lamp='lamp01', on=True)
        acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time=1.0)
        lamp_switch(lamp='lamp01', on=False)
        print("Spectrometer and lamp checked successfully.")
    except Exception as e:
        print(f"Error checking spectrometer or lamp: {e}")

