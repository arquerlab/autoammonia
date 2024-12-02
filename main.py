from prefect import flow, task, get_run_logger
import json
import time
from typing import Dict, List, Optional, Any

from decorators import with_lock
from default_config import DEFAULT_CONFIG, CONNECTIONS_INFO
from redis_client import client, client_initialization
from Amonia_SDL_v02 import initialize_pump, restore_pump


@task
@with_lock(acquisition_timeout=5,function_timeout=5)
def fetch_task_from_redis(list_name: str) -> Optional[Dict[str, str]]:
    """
    Fetch a task from the Redis queue.
    
    Args:
        list_name (str): Redis variable where experiments data will taken from.

    Returns:
        dict: The task as a dictionary if found, or None if the queue is empty.
    """
    experiment = client.lpop(list_name)  # Fetch the first task from the queue
    logger = get_run_logger()
    logger.info(f'Current first element: {experiment}')
    if experiment:
        return json.loads(experiment)  # Convert the experiment to a dictionary
    return None


@task
def execute_experiment(experiments: List[Dict[str, str]]) -> None:
    """
    Simulates the execution of an experiment using multiple tasks.

    Args:
        experiments (list): A list of task dictionaries, each containing 'composition' and 'electrolyte'.
    """
    logger = get_run_logger()
    for idx, experiment in enumerate(experiments, start=1):
        composition = experiment["composition"]
        electrolyte = experiment["electrolyte"]
        logger.info(f"Running experiment with Cell {idx}: Composition {composition}, Electrolyte {electrolyte}")
    time.sleep(5)  # Simulates the execution time of the experiment
    logger.info("Experiment complete!")


@task
def should_stop() -> bool:
    """
    Check a Redis key to determine if the flow should stop.

    Returns:
        bool: True if the stop signal is present, False otherwise.
    """
    return client.get("stop_signal") == b"1"


@flow
def process_experiment_queue(delete_previous_queue: Optional[bool] = None,
                             parallel_cells: Optional[int] = None,
                             **kwargs: Any
) -> None:
    """
    Main flow for the set up. It processes the 'experiiment_queue' in Redis. Waits until the 
    required number of tasks are available before executing an experiment. Additionally, initializes 
    syringe pumps at the beginning and restores them to their default state when the flow ends.

    Continuously checks the Redis queue for tasks. Fetches tasks equal to the `parallel_cells` value 
    and executes them together. If fewer tasks are available, waits for the remaining tasks to arrive.

    Args:
        delete_previous_queue (bool, optional): Whether to clear the Redis queue at the start of the flow.
            Defaults to the value in `DEFAULT_CONFIG['delete_previous_queue']`.
        parallel_cells (int, optional): Number of tasks to process in parallel. Defaults to the value in 
            `DEFAULT_CONFIG['parallel_cells']`.
        **kwargs (Any): Additional keyword arguments that can override the default configuration settings.

    Stop Logic:
        The flow can be stopped manually (Ctrl + C) or by setting the `stop_signal` key in Redis.
    """
    delete_previous_queue = delete_previous_queue if delete_previous_queue is not None else DEFAULT_CONFIG[
        'delete_previous_queue']
    parallel_cells = parallel_cells if parallel_cells is not None else DEFAULT_CONFIG['parallel_cells']

    if delete_previous_queue:
        client.delete("experiment_queue")
    client_initialization(**kwargs)
    
    syringe_pumps = []
    for pump in CONNECTIONS_INFO:
        if 'tecan' in pump:
            syringe_pumps.append(pump)
    for pump in syringe_pumps:
        initialize_pump(syringe_pump=pump, **kwargs)
        pass

    logger = get_run_logger()
    client.set("stop_signal",0)
    
    try:
        while True:
            if should_stop():
                logger.info("Stop signal received. Exiting flow.")
                break

            experiments = []  # List to hold fetched tasks
            while len(experiments) < parallel_cells:
                experiment = fetch_task_from_redis("experiment_queue")
                if experiment:
                    experiments.append(experiment)
                    logger.info(f"Fetched task {len(experiments)} of {parallel_cells} from the queue.")
                else:
                    logger.info(f"Waiting for tasks... Currently fetched: {len(experiments)} of {parallel_cells}.")
                    time.sleep(10)

            # Execute the experiment once enough tasks are available
            logger.warning(experiments)
            execute_experiment(experiments, **kwargs)
    finally:
        for pump in syringe_pumps:
            restore_pump(syringe_pump=pump, **kwargs)
            pass
        logger.info("Flow stopped. All syringe pumps restored to their default state.")


if __name__ == '__main__':
    process_experiment_queue(delete_previous_queue=True)
