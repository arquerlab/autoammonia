from autoammonia.reaction_steps import empty_and_stop_pumps
from autoammonia.hardware.syringe_pumps import syringe_draw_and_dispense_volume
from autoammonia.reaction_steps import wash_flow_cell
from autoammonia.hardware.selection_valves import switch_port_valve
from autoammonia.hardware.peristaltic_pumps import run_pump, stop_pump
from autoammonia.utils.redis_client import client
import time

"""syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=8, draw_valve_port='water', dispense_valve_port='WEvial01', speed=1)
syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=8, draw_valve_port='water', dispense_valve_port='CEvial01', speed=1)

run_pump(pump='longerWE01', speed=1, direction=False)
run_pump(pump='longerCE01', speed=1, direction=False)
time.sleep(300)
empty_and_stop_pumps(wash_time=90, pump_speed=1.8)"""
syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=20, draw_valve_port='WEvial01', dispense_valve_port='waste', speed=1)
syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=20, draw_valve_port='CEvial01', dispense_valve_port='waste', speed=1)
