import toml
from pathlib import Path
from .config import CONNECTIONS_INFO

MOCK_OVERRIDES = {
    "matterlab_pumps.LongerPeristalticPump": "autoammonia.hardware.mock.longer_mock.LongerPeristalticPumpMock",
    "matterlab_pumps.TecanXCPump": "autoammonia.hardware.mock.tecan_mock.TecanXCPumpMock",
    "matterlab_valves.ValcoSelectionValve": "autoammonia.hardware.mock.valco_mock.ValcoSelectionValveMock",
    "pyBEEP.PotentiostatController": "autoammonia.hardware.mock.pyBEEP_mock.PotentiostatControllerMock",
    "pyBEEP.PotentiostatDevice": "autoammonia.hardware.mock.pyBEEP_mock.PotentiostatDeviceMock",
    "matterlab_spectrometers.HamamatsuMiniSpectrometer": "autoammonia.hardware.mock.hamamatsu_mock.HamamatsuMiniSpectrometerMock",
    "autoammonia.hardware.uv_vis_lamp.Arduino": "autoammonia.hardware.mock.lamp_mock.ArduinoMock",
    "autoammonia.hardware.uv_vis_lamp.MotorSwitchLamp": "autoammonia.hardware.mock.lamp_mock.MotorSwitchLampMock",
    "autoammonia.hardware.uv_vis_lamp.PulsedLamp": "autoammonia.hardware.mock.lamp_mock.PulsedLampMock",
}

_config_components = toml.load(Path(__file__).parent / "components.toml")
simulation = _config_components.pop('global', {}).get('simulation', False)

def get_config_components() -> dict[str, dict]:
    """
    Return the raw component configs with class names optionally replaced by mocks.
    Classes are NOT resolved/imported yet.
    Adds dynamic 'ports' info from CONNECTIONS_INFO if present.
    """
    result = {}
    for name, cfg in _config_components.items():
        if name == "global":
            continue

        cfg = cfg.copy()

        # Replace class/device_class with mock version if in simulation mode
        for key in ("class", "device_class"):
            if key in cfg:
                target = cfg[key]
                if simulation and target in MOCK_OVERRIDES:
                    cfg[key] = MOCK_OVERRIDES[target]

        # Add 'ports' info if available
        if name in CONNECTIONS_INFO:
            cfg["ports"] = {
                port: CONNECTIONS_INFO[name][port]["port"]
                for port in CONNECTIONS_INFO[name]
            }

        result[name] = cfg

    return result

CONFIG_COMPONENTS = get_config_components()