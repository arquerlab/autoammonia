from typing import Optional, Dict, Union

class ValcoSelectionValveMock:
    def __init__(self,
                 com_port: str,
                 num_port: int,
                 baudrate: int = 9600,
                 ports: Optional[Dict[str, int]] = None,
                 ):
        self.num_port = num_port
        self.ports: Optional[Dict[str, int]] = ports if ports else {}
        self.com_port = com_port
        self.baudrate = baudrate
        self.port = 1

    def switch_port(self, port: Union[str, int]) -> int:
        if isinstance(port, str):
            port = self.ports.get(port)
        if port is not None:
            self.port = port
            return port
        else:
            raise ValueError('Wrong ports')
    
    
