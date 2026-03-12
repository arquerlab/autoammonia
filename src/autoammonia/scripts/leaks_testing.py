from prefect import flow
from typing import Any

from ..utils.decorators import with_lock
from ..hardware.syringe_pumps import compartment_fill, compartment_wash, syringe_draw_and_dispense_volume
from ..hardware.peristaltic_pumps import run_pump, stop_pump
from ..config.config import DEFAULT_CONFIG

@flow
def leaks_testing(**kwargs: Any):
    """
    Tests for leaks in the flow cell by running pumps and checking for leaks.
    Args:
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    wash_comp_volume = config['wash_flow_cell_wash_comp_volume']
    
    #compartment_fill(syringe_pump='tecanRX01', source='water', destination='WEvial01', volume=10, speed=2)
    #compartment_fill(syringe_pump='tecanRX01', source='water', destination='CEvial01', volume=10, speed=2)
    #syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=10, draw_valve_port='water', dispense_valve_port='WEvial01', speed=2)
    #syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=10, draw_valve_port='water', dispense_valve_port='CEvial01', speed=2)
    while True:
        run_pump(pump='longerWE01', speed=2, direction=False)
        run_pump(pump='longerCE01', speed=2, direction=False)
        print("Pumps running, press Enter to stop")
        input()
        stop_pump(pump='longerWE01')
        stop_pump(pump='longerCE01')
        print("Pumps stopped")
        print("Press Enter or type 'r' to restart pumps")
        inp = input()
        if inp != '':
            break

    """
    compartment_wash(syringe_pump='tecanRX01', compartment=f'WEvial01', repeats=0,
                             wash_vol=wash_comp_volume, speed=0.8,
                             speed_last_empty=0.2, **kwargs)
    compartment_wash(syringe_pump='tecanRX01', compartment=f'CEvial01', repeats=0,
                             wash_vol=wash_comp_volume, speed=0.8,
                             speed_last_empty=0.2, **kwargs)
    """