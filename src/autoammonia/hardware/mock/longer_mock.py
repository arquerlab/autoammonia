from typing import Dict, Union


class LongerPeristalticPumpMock:
    def __init__(
            self,
            com_port: str,
            address: int,
            baudrate: int = 9600,
        ) -> None:
        if baudrate != 1200:
            raise ValueError("Longer mock only supports 1200 baudrate")
        self.address = address
        self.com_port = com_port
        self.rpm = 0.
        self.on = False
        self.direction = False

    def set_pump(
            self,
            rpm: float | None = None,
            on: bool | None = None,
            direction: bool | None = None,
    ) -> None:
        self.rpm = rpm if rpm is not None else self.rpm
        self.on = on if on is not None else self.on
        self.direction = direction if direction is not None else self.direction
        print(f"[LongerPeristalticPumpMock] Setting pump at address {self.address} with rpm={rpm}, on={on}, direction={direction}")

    def query_pump(self) -> Dict[str, Union[float, bool]]:
        print(f"[LongerPeristalticPumpMock] Querying pump at address {self.address}\n")
        return {"rpm": self.rpm, "on": self.on, "direction": self.direction}
        
        
        