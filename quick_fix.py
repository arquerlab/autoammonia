from prefect.variables import Variable
import asyncio

from autoammonia.hardware.syringe_pumps import syringe_draw_and_dispense_volume, compartment_fill
from autoammonia.hardware.selection_valves import switch_port_valve
from autoammonia.hardware.peristaltic_pumps import run_pump, stop_pump
from autoammonia.hardware.potentiostat import run_method_parallel
from autoammonia.reaction_steps import empty_and_stop_pumps
import time

run_pump(pump='longerWE01', speed=1, direction=False)
run_pump(pump='longerCE01', speed=1, direction=False)
time.sleep(20)
asyncio.run(run_method_parallel(parallel_cells=1, folder='C:/Users/LAB-CO2MAP/autoammonia_data',
                            experiment_ids=[147,], mode="CP", params= {'current': 0.0028, 'duration': 20}, 
                            tia_gain=0,))
empty_and_stop_pumps(wash_time=30, pump_speed=1.4)