import asyncio
from typing import Optional, Any, Dict
from prefect import task, flow

from ..utils.decorators import run_on_component_with_lock
from ..config.config import DEFAULT_CONFIG

@flow
async def run_echem_method(
        potentiostat: str,
        mode: str,
        method_params: Dict[str, Any],
        tia_gain: int,
        reducing_factor: int | None,
        filename: str,
        folder: str,    
        acquisition_timeout: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Runs an electrochemical measurement method on a potentiostat in a thread-safe manner.

    This function applies an electrochemical method (such as chrono-potentiometry) with the given parameters
    on the specified potentiostat. A lock mechanism ensures exclusive access to the potentiostat resource during the measurement.
    If the operation fails after retries, a RuntimeError is raised and the safety flag may trigger an emergency stop.

    Args:
        potentiostat (str): Identifier or instance of the potentiostat to use for the experiment.
        mode (str): Measurement mode key (e.g., 'CA', 'CV', etc.).
        method_params (Dict[str, Any]): Dictionary of parameters for the measurement waveform.
        tia_gain (int): Gain setting for the transimpedance amplifier (typically 0–4).
        reducing_factor (int): If set, averages every N rows before saving (data reduction).
        filename (str): Name of the file where data will be stored.
        folder (str): Directory where the data file will be saved.
        acquisition_timeout (Optional[int]): Timeout for acquiring the lock, in seconds. Defaults to config['potentiostat_acq_timeout'].
        **kwargs: Additional configuration options.
    """
    config = {**DEFAULT_CONFIG,**kwargs}
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['potentiostat_acq_timeout']
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout= 600)
    def run_method(potentiostat: str, mode: str, params: Dict[str, Any], tia_gain: int, reducing_factor: int | None, filename: str, folder: str) -> None:
        potentiostat.apply_measurement(mode=mode, params=params, tia_gain=tia_gain, reducing_factor=reducing_factor, filename=filename, folder=folder)

    # Call the wrapped function
    run_method(potentiostat=potentiostat, mode=mode, params=method_params, tia_gain=tia_gain, reducing_factor=reducing_factor, filename=filename, folder=folder)

@flow
async def run_method_parallel(parallel_cells: int,
                      folder: str,
                      experiment_id: str,
                      mode: str,
                      params: Dict[str, Any],
                      tia_gain: int,
                      reducing_factor: int | None = None,
                      **kwargs,
)->None:
    """
    Runs an electrochemical measurement method in parallel for multiple cells.

    This function launches concurrent electrochemical experiments, each on a separate potentiostat
    with the specified parameters, and waits for all to complete.

    Args:
        parallel_cells (int): Number of cells/potentiostats to run in parallel.
        folder (str): Directory where all data files will be stored.
        experiment_id (str): Unique identifier for the experiment (used in filenames).
        mode (str): Measurement mode key (e.g., 'CA', 'CV', etc.).
        params (Dict[str, Any]): Dictionary of measurement parameters to use for each cell.
        tia_gain (int): Gain setting for the transimpedance amplifier.
        reducing_factor (int): If set, averages every N rows before saving (data reduction).
        **kwargs: Additional configuration options.
    """
    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [experiment_id + f'_cell{str(cell).zfill(2)}.csv' for cell in
                 range(1, parallel_cells + 1)]
    tasks = [asyncio.create_task(run_echem_method(potentiostat=potentiostats[i],mode=mode, method_params=params,
                                        tia_gain=tia_gain, reducing_factor=reducing_factor, 
                                                  filename=filenames[i], folder=folder, **kwargs))
             for i in range(parallel_cells)]

    # Wait until the first asyncio task completes
    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    # Get the result from the completed task(s)
    for completed_task in done:
        result = await completed_task
        print(f"Completed: {result}")
