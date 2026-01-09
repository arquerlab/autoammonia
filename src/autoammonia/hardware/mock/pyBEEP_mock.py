from typing import List, Any, Dict, Optional
from time import sleep

from pyBEEP.measurement_modes.measurement_modes import ModeName, ControlMode, MeasurementMode, MeasurementModeMap
from pyBEEP.measurement_modes.waveform_params import (
    ConstantWaveformParams, PotentialStepsParams, LinearSweepParams, CyclicVoltammetryParams,
    SinglePointParams, CurrentStepsParams, LinearGalvanostaticSweepParams, CyclicGalvanostaticParams, OCPParams
)

# Dummy waveform functions to simulate pyBEEP behavior
def mock_waveform(*args, **kwargs):
    return "mock_waveform_data"

constant_waveform = potential_steps = linear_sweep = cyclic_voltammetry = mock_waveform
single_point = current_steps = linear_galvanostatic_sweep = cyclic_galvanostatic = mock_waveform


class PotentiostatDeviceMock:
    """Mock for the physical potentiostat device."""
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
    """Mock for the pyBEEP PotentiostatController."""
    def __init__(self, device, default_folder: str | None = None):
        self.device = device
        self.default_folder = default_folder
        self.last_plot_path = None

        # Map modes to their respective parameter classes and mock functions
        # This matches the structure in the real pyBEEP MeasurementModeMap
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
        """
        Mock implementation of apply_measurement.
        Validates params against the real pyBEEP parameter classes.
        """
        print(f"[MOCK] apply_measurement called with mode={mode}")
        
        mode_upper = mode.upper()
        if mode_upper not in self._measurement_modes:
            raise ValueError(f"[MOCK] Unknown mode '{mode}'")

        mode_info = self._measurement_modes[mode_upper]
        param_class = mode_info["param_class"]
        waveform_func = mode_info["waveform_func"]

        # CRITICAL: This line validates that the params dictionary matches the real pyBEEP requirement
        # If 'params' is missing a required field or has an extra one, this will raise a TypeError
        # just like the real library would.
        try:
            validated_params = param_class(**params)
            print(f"[MOCK] Params validated successfully for {mode_upper}")
        except TypeError as e:
            print(f"[MOCK] Param validation FAILED for {mode_upper}: {e}")
            raise

        # Simulate waveform generation
        waveform = waveform_func(**params)
        print(f"[MOCK] Generated waveform: {waveform}")

        # Simulate execution time
        duration = params.get('duration', 1.0) # Default to 1s for mock speed
        print(f"[MOCK] Simulating measurement for {duration} seconds...")
        sleep(duration)

        # Set the result path
        self.last_plot_path = f"{folder or 'mock_folder'}/{filename or f'mock_{mode}.csv'}"
        print(f"[MOCK] Measurement complete. Results saved to {self.last_plot_path}")
