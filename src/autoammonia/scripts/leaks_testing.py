from prefect import flow

from ..utils.decorators import with_lock
from ..hardware.syringe_pumps import compartment_fill, compartment_wash
from ..hardware.peristaltic_pumps import run_pump, stop_pump

@flow
def leaks_testing():
    compartment_fill(syringe_pump='tecanRX01', source='water', destination='WEvial01', volume=10, speed=2)
    compartment_fill(syringe_pump='tecanRX01', source='water', destination='CEvial01', volume=10, speed=2)

    while True:
        run_pump(pump='longerWE01', speed=5, direction=True)
        run_pump(pump='longerCE01', speed=5, direction=True)
        print("Pumps running, press Enter to stop")
        input()
        stop_pump(pump='longerWE01')
        stop_pump(pump='longerCE01')
        print("Pumps stopped")
        print("Press Enter or type 'r' to restart pumps")
        inp = input()
        if inp != '':
            break
    
    compartment_wash(syringe_pump='tecanRX01', compartment='WEvial01', repeats=0, speed=2)
    compartment_wash(syringe_pump='tecanRX01', compartment='CEvial01', repeats=0, speed=2)

