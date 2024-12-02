import asyncio
from typing import Optional, Any
from prefect import task, flow

from decorators import run_on_component_with_lock
from default_config import DEFAULT_CONFIG

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
                      data_path: str,
                      experiment_id: str,
                      current: float,
                      time_rx: float,
                      tia_gain: int,
)->None:
    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [data_path + '/' + experiment_id + f'_cell{str(cell).zfill(2)}.csv' for cell in
                 range(1, parallel_cells + 1)]
    tasks = [asyncio.create_task(run_cp(potentiostat_cp=potentiostats[i],current_cp=current,time_rx_cp=time_rx,
                                        tia_gain_cp=tia_gain, filepath_cp=filenames[i]))
             for i in range(parallel_cells)]

    # Wait until the first asyncio task completes
    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    # Get the result from the completed task(s)
    for completed_task in done:
        result = await completed_task
        print(f"Completed: {result}")
