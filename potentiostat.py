import asyncio
from typing import Optional, Any
from prefect import task

from decorators import run_on_component_with_lock
from default_config import DEFAULT_CONFIG

@flow
async def run_cp(
        potentiostat: str,
        current: float,
        time_rx: float,
        tia_gain: int,
        filepath: str,
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
        potentiostat (str): The potentiostat used for the experiment.
        current (float): The current to apply (in A).
        time_rx (float): Duration to apply the current (in seconds).
        acquisition_timeout (Optional[int]): Timeout for acquiring the lock. Defaults to config['potentiostat_lock_timeout']
        **kwargs (Any): Additional configuration options.
    """
    config = {**DEFAULT_CONFIG,**kwargs}
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['potentiostat_acq_timeout']
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout= int(time_rx * 1.1))
    def run_cp_func(potentiostat: str, current: float, time_rx: float, tia_gain: int, filepath:str) -> None:
        potentiostat.apply_cp(current=current, time=time_rx, tia_gain=tia_gain, filepath=filepath)

    # Call the wrapped function
    run_cp_func(potentiostat=potentiostat, current=current, time_rx=time_rx,tia_gain=tia_gain, filepath=filepath)

@flow
async def run_cp_iter(parallel_cells: int, data_path: str, experiment_id: str):
    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [data_path + '/' + experiment_id + f'_cell{str(cell).zfill(2)}.csv' for cell in
                 range(1, parallel_cells + 1)]
    tasks = [asyncio.create_task(run_cp(potentiostat=potentiostats[i],current=current,time_rx=time_rx,
                                        tia_gain=tia_gain, filepath=filenames[i]))
             for i in range(1,parallel_cells+1)]

    # Wait until the first asyncio task completes
    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    # Get the result from the completed task(s)
    for completed_task in done:
        result = await completed_task
        print(f"Completed: {result}")
