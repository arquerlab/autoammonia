import time
from math import ceil
from typing import Union, Optional, Dict

from matterlab_pumps import TecanXCPump

class TecanXCPumpMock():
    def __init__(self,
                 com_port: str,
                 address: Union[str, int],
                 syringe_volume: float,
                 num_valve_port: int,
                 init_valve: int = 1,
                 out_valve: int = 12,
                 ports: Optional[Dict[str, int]] = None
                 ):
        if (init_valve > num_valve_port + 1) or (out_valve > num_valve_port + 1):
            raise ValueError("Init_valve or Out valve_num exceed num_valve_port!")
        self.com_port = com_port
        self.address = address
        self.syringe_volume = syringe_volume
        self.num_valve_port = num_valve_port
        self.ports: Optional[Dict[str, int]] = ports if ports else {}
        self.volume = 0.0

    def draw(self, volume: float, valve_port: Optional[Union[int, str]] = None, speed: Optional[float] = None) -> None:
        assert volume > 0, "Draw volume must be positive"
        current_volume = self.volume
        if (volume + current_volume) > (1.001e3 * self.syringe_volume):
            raise ValueError("Draw volume excess syringe size")
        self.volume = current_volume + volume
        print('[TecanXCPumpMock] Drawing volume:', volume, 'mL')

    def dispense(self, volume: float, valve_port: Optional[Union[int, str]] = None,
                 speed: Optional[float] = None) -> None:
        assert volume > 0, "Dispense volume must be positive"
        current_volume = self.volume
        if volume > (current_volume + self.syringe_volume):
            raise ValueError('Dispense volume excess amount in syringe')
        self.volume = current_volume - volume
        print('[TecanXCPumpMock] Dispensing volume:', volume, 'mL')

    def draw_and_dispense(
            self,
            volume: float,
            draw_valve_port: Union[int, str] = None,
            dispense_valve_port: Union[int, str] = None,
            speed: Optional[float] = None,
            wait: float = 0
    ) -> None:
        dispense_iterations = ceil(volume / (1e3 * self.syringe_volume))
        volume_per_iteration = volume / dispense_iterations
        for i in range(0, dispense_iterations):
            self.draw(volume=volume_per_iteration, valve_port=draw_valve_port, speed=speed)
            time.sleep(wait)
            self.dispense_all(valve_port=dispense_valve_port, speed=speed)
            time.sleep(wait)
            
    def draw_full(self, **kwargs) -> None:
        current_volume = self.volume
        draw_volume = self.syringe_volume * 1e3 - current_volume
        self.draw(volume=draw_volume, **kwargs)

    def dispense_all(self, **kwargs) -> None:
        current_volume = self.volume
        self.dispense(volume=current_volume, **kwargs)