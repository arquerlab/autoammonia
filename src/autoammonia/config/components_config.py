simulation = True

if simulation:
    from ..hardware.mock.longer_mock import LongerPeristalticPumpMock as LongerPeristalticPump
    from ..hardware.mock.tecan_mock import TecanXCPumpMock as TecanXCPump
    from ..hardware.mock.valco_mock import ValcoSelectionValveMock as ValcoSelectionValve
    from ..hardware.mock.pyBEEP_mock import PotentiostatDeviceMock as PotentiostatDevice
    from ..hardware.mock.pyBEEP_mock import PotentiostatControllerMock as PotentiostatController
    #from ..hardware.mock.hamamatsu_mock import HamamatsuMiniSpectrometerMock as HamamatsuMiniSpectrometer
else:
    from matterlab_pumps import TecanXCPump, LongerPeristalticPump
    from matterlab_valves import ValcoSelectionValve
    from pyBEEP import PotentiostatDevice, PotentiostatController
    # from matterlab_spectrometers import HamamatsuMiniSpectrometer
    # from ..hardware.uv_vis_lamp import Arduino, MotorSwitchLamp, PulsedLamp

CONFIG_COMPONENTS = {'longerWE01': {'class': LongerPeristalticPump, 'com_port': '/dev/longer_pumps', 'address': 1, 'baudrate': 1200},
                     'longerCE01': {'class': LongerPeristalticPump, 'com_port': '/dev/longer_pumps', 'address': 2, 'baudrate': 1200},
                     'tecanRX01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 2, 'syringe_volume': 2.5e-3,
                                   'num_valve_port': 12,
                                   'ports': None},
                     'valveRX01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveRX01', 'num_port':10,
                                   'ports': None},
                     'tecanAZ01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 1, 'syringe_volume': 1e-3,
                                   'num_valve_port': 12,
                                   'ports': None},
                     'valveAZ01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveAZ01','num_port':10,
                                   'ports': None},
                     'potentiostat01': {'class': PotentiostatController, 'device_class': PotentiostatDevice,'device_kwargs': {'port': '/dev/potentiostat01', 'address': 1}},
                     #'UVVIS01':{'class': HamamatsuMiniSpectrometer},
                     #'lamp01': {'class': Arduino, 'device_class': MotorSwitchLamp, 'com_port': 'COM5', 'pulsed': False}
                     }