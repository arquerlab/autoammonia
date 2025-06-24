from prefect import flow, task
import pandas as pd

from ..utils.decorators import run_on_component_with_lock

@run_on_component_with_lock
@task
def lamp_switch(lamp: str, on: bool=True) -> None:
    """
    Switches on/off the lamp used for UV-Vis measurements.
    
    Args:
        lamp (str): The lamp to switch on or off.
    """
    if on:
        lamp.start()
    else:
        lamp.stop()
        
@run_on_component_with_lock
@flow
def acquire_spectrum(
        spectrometer: str,
        lamp: str,
        integration_time: float,
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
        