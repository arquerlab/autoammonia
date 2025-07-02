from prefect import flow, task, get_run_logger
import pandas as pd
from typing import Any

from ..utils.decorators import run_on_component_with_lock
from ..config.config import DEFAULT_CONFIG


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
        
@task
def spec_acquire(
        spectrometer: str,
        integration_time: float | int,
        retries: int | None = None, 
        **kwargs: Any,
) -> pd.DataFrame:
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['uv_vis_retries']
    function_timeout = integration_time + 5
    logger = get_run_logger()
    
    @task
    @run_on_component_with_lock(function_timeout=function_timeout)
    def spec_acquire_func(
            spec: str,
            integration: float | int,
    ) -> pd.DataFrame:
        wavelength = spec.wavelength
        data = spec.measure_spectrum(integration)
        df = pd.DataFrame({
            "Wavelength (nm)": wavelength,
            "Intensity": data
        })
        return df
    
    try:
        output = spec_acquire_func.with_options(retries=retries)(spectrometer, integration_time)
        logger.info(f"[{spectrometer}] Adsoption spectra acquired succesfully")
        return output
    except Exception as e:
        logger.error(f"[{spectrometer}] Failed to acquire absorption spectrum after {retries} retries: {e}")
        raise
    
    

@flow
def acquire_spectrum(
        spectrometer: str,
        lamp: str,
        integration_time: float | int,
) -> pd.DataFrame:
    lamp_switch(lamp=lamp, on=True)
    df = spec_acquire(spectrometer=spectrometer, integration_time=integration_time)
    lamp_switch(lamp=lamp, on=False)
    return df
        