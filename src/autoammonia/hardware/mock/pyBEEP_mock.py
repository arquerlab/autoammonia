from typing import List

from pyBEEP.waveform_params import (
    ConstantWaveformParams, PotentialStepsParams, LinearSweepParams, CyclicVoltammetryParams,
    SinglePointParams, CurrentStepsParams, LinearGalvanostaticSweepParams, CyclicGalvanostaticParams
)
from pyBEEP.waveforms_pot import constant_waveform, potential_steps, linear_sweep, cyclic_voltammetry
from pyBEEP.waveforms_gal import single_point, current_steps, linear_galvanostatic_sweep, cyclic_galvanostatic


class PotentiostatDeviceMock:
    def __init__(self, port: str, address: int, baudrate: int = 1500000, timeout: float = 0.03):
        self.port = port
        self.address = address
        self.baudrate = baudrate
        self.timeout = timeout
        print(f"[MOCK] Potentiostat initialized at port={port}, address={address}, baudrate={baudrate}, timeout={timeout}")

    def send_command(self, command: int, parameter: int = 0) -> None:
        print(f"[MOCK] send_command(command={command}, parameter={parameter})")

    def write_data(self, address: int, data: List[int]) -> None:
        print(f"[MOCK] write_data(address={address}, data={data})")

    def read_data(self, address: int, count: int) -> List[int]:
        print(f"[MOCK] read_data(address={address}, count={count})")
        return [0] * count  # return dummy data
    
class PotentiostatControllerMock:
    def __init__(self, device, default_folder: str | None = None):
        self.device = device
        self.default_folder = default_folder
        self.last_plot_path = None

        self._measurement_modes = {
            "CA": {"pid": False, "waveform_func": constant_waveform, "param_class": ConstantWaveformParams},
            "LSV": {"pid": False, "waveform_func": linear_sweep, "param_class": LinearSweepParams},
            "CV": {"pid": False, "waveform_func": cyclic_voltammetry, "param_class": CyclicVoltammetryParams},
            "PSTEP": {"pid": False, "waveform_func": potential_steps, "param_class": PotentialStepsParams},

            "CP": {"pid": True, "waveform_func": single_point, "param_class": SinglePointParams},
            "GS": {"pid": True, "waveform_func": linear_galvanostatic_sweep,
                   "param_class": LinearGalvanostaticSweepParams},
            "GCV": {"pid": True, "waveform_func": cyclic_galvanostatic, "param_class": CyclicGalvanostaticParams},
            "STEPSEQ": {"pid": True, "waveform_func": current_steps, "param_class": CurrentStepsParams},
        }

    def apply_measurement(
        self,
        mode: str,
        params: dict,
        *,
        tia_gain: int = 0,
        reducing_factor: int | None = None,
        filename: str | None = None,
        folder: str | None = None
    ):
        print(f"[MOCK] apply_measurement called with:")
        print(f"       mode={mode}, tia_gain={tia_gain}, filename={filename}, folder={folder}")
        print(f"       params={params}, reducing_factor={reducing_factor}")

        mode_upper = mode.upper()
        if mode_upper not in self._measurement_modes:
            raise ValueError(f"[MOCK] Unknown mode '{mode}'")

        waveform_func = self._measurement_modes[mode_upper]["waveform_func"]
        waveform = waveform_func(**params)

        print(f"[MOCK] Generated waveform: {waveform}")
        self.last_plot_path = f"{folder or 'mock_folder'}/{filename or f'mock_{mode}.csv'}"
    
    