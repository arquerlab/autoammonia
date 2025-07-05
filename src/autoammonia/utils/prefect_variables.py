from prefect.variables import Variable
from ..config.config import CONNECTIONS_INFO

def initialize_prefect_variables(overwrite: bool = False) -> None:
    simplified = {
        port: {
            'volume': port_dict['volume'],
            'max_vol': port_dict['max_vol']
        }
        for device_dict in CONNECTIONS_INFO.values()
        for port, port_dict in device_dict.items()
        if port != 'air' and 'valve' not in port
    }
    for key, value in simplified.items():
        try:
            Variable.set(key.lower(), value, overwrite=overwrite)
        except ValueError:
            pass