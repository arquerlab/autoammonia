import asyncio
from typing import Optional, Any
from prefect import task, flow

from ..utils.decorators import run_on_component_with_lock
from ..config.config import DEFAULT_CONFIG

@flow
async def run_cp(
        potentiostat_cp: str,
        current_cp: float,
        time_rx_cp: float,
        tia_gain_cp: int,
        filepath_cp: str,
        acquisition_timeout: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Runs chrono-potentiometry by applying a constant current for a specified duration.
    
    This function wraps the pump operation with a lock mechanism, ensuring that the pump 
    resource is accessed in a thread-safe manner. If the operation fails after the retries, 
    a `RuntimeError` is raised and the flag 'safety_operation' is set to 0 in redis, which
    will trigger the emergency_stop function.

    Args:
        potentiostat_cp (str): The potentiostat used for the experiment.
        current_cp (float): The current to apply (in A).
        time_rx_cp (float): Duration to apply the current (in seconds).
        tia_gain_cp (int): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm].
                This parameter is generally referred in commercial potentiostats as current/potential range.
        filepath_cp (str): Path where data is meant to be stored.
        acquisition_timeout (Optional[int]): Timeout for acquiring the lock. Defaults to config['potentiostat_lock_timeout']
        **kwargs (Any): Additional configuration options.
    """
    config = {**DEFAULT_CONFIG,**kwargs}
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['potentiostat_acq_timeout']
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout= int(time_rx_cp * 1.1))
    def run_cp_func(potentiostat: str, current: float, time_rx: float, tia_gain: int, filepath:str) -> None:
        potentiostat.apply_cp(current=current, time=time_rx, tia_gain=tia_gain, filepath=filepath)

    # Call the wrapped function
    run_cp_func(potentiostat=potentiostat_cp, current=current_cp, time_rx=time_rx_cp, tia_gain=tia_gain_cp,
                filepath=filepath_cp)

@flow
async def run_cp_iter(parallel_cells: int,
                      data_path: Path,
                      experiment_id: str,
                      current: float,
                      time_rx: float,
                      tia_gain: int,
                      **kwargs,
)->None:
    """
    Runs chrono-potentiometry for multiple cells concurrently by applying a constant current for each cell.

    This function manages the execution of multiple chrono-potentiometry experiments in parallel, each
    running on a separate potentiostat.

    Args:
        parallel_cells (int): Number of cells to run the experiment on.
        data_path (str): Folder where the data will be stored.
        experiment_id (str): Unique identifier for the experiment.
        current (float): The current to apply (in A).
        time_rx (float): Duration to apply the current (in seconds).
        tia_gain (int): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm].
                This parameter is generally referred in commercial potentiostats as current/potential range.
        **kwargs (Any): Additional configuration options.
    """
    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [data_path + '/' + experiment_id + f'_cell{str(cell).zfill(2)}.csv' for cell in
                 range(1, parallel_cells + 1)]
    tasks = [asyncio.create_task(run_cp(potentiostat_cp=potentiostats[i],current_cp=current,time_rx_cp=time_rx,
                                        tia_gain_cp=tia_gain, filepath_cp=filenames[i], **kwargs))
             for i in range(parallel_cells)]

    # Wait until the first asyncio task completes
    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    # Get the result from the completed task(s)
    for completed_task in done:
        result = await completed_task
        print(f"Completed: {result}")
