import numpy as np
from typing import Union, List, Tuple


class HamamatsuMiniSpectrometerMock:
    def __init__(self,
                 product_id: Union[str, int] = "J4245013",   # J4245013 for SDL2 default
                 calibration_coefficient: List = [1.599374522e2, 3.000949820e-1, 1.964555833e-5, 4.685973475e-10, -1.010224773e-12, 8.932925939e-17]    # default for SDL2
                 ):
        self.product_id = product_id
        self._pixel_number = 2048
        self.wavelength_calibration(calibration_coefficient)
        
    def wavelength_calibration(self, calibration_coefficient: Union[np.ndarray, List, Tuple]) -> None:
        """
        Create the wavelength calibration
        :param calibration_coefficient: calibration coefficient given by factory
        :return: calibrated wavelength
        """
        pix = np.arange(1, self._pixel_number+1)
        self._wavelength = np.polyval(calibration_coefficient[::-1], pix)

    @property
    def wavelength(self) -> np.ndarray:
        """
        Get the calibrated wavelength
        :return: calibrated wavelength
        """
        return self._wavelength

    def measure_spectrum(self, integration_time: float) -> np.ndarray:
        rtn = np.zeros(2048, dtype=np.uint32)
        print(f"[HamamatsuMiniSpectrometerMock] Measuring spectrum with integration time {integration_time} ms")
        return(rtn)
        



