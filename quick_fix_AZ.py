from autoammonia.hardware.syringe_pumps import syringe_draw_and_dispense_volume
from autoammonia.hardware.syringe_pumps import syringe_draw
from autoammonia.hardware.syringe_pumps import syringe_dispense

for i in range(10):
    syringe_draw(syringe_pump='tecanAZ01', volume=1, valve_port='water', speed=0.2)
    syringe_dispense(syringe_pump='tecanAZ01', volume=1, valve_port='WEvial01', speed=1)
syringe_draw_and_dispense_volume(syringe_pump='tecanRX01', volume=16, draw_valve_port='WEvial01', dispense_valve_port='waste', speed=0.2)
