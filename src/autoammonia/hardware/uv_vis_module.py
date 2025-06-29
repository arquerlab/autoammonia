from prefect import flow, task
import pandas as pd

from ..utils.decorators import run_on_component_with_lock

@task
@run_on_component_with_lock()
def lamp_switch(lamp: str, on: bool=True) -> None:
    """
    Switches on/off the lamp used for UV-Vis measurements.
    
    Args:
        lamp (str): The lamp to switch on or off.
        on (bool): If True, the lamp is turned on; if False, it is turned off.
    """
    if on:
        lamp.start()
    else:
        lamp.stop()

@flow
@run_on_component_with_lock()
def acquire_spectrum(
        spectrometer: str,
        lamp: str,
        integration_time: float | int,
) -> pd.DataFrame:
    lamp_switch(lamp=lamp, on=True)
    wavelength = spectrometer.wavelength
    data = spectrometer.measure_spectrum(integration_time)
    lamp_switch(lamp=lamp, on=False)

    df = pd.DataFrame({
        "Wavelength (nm)": wavelength,
        "Intensity": data
    })
    return df
        