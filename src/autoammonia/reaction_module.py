from prefect import flow, task, get_run_logger
import json
import time
from typing import Dict, Optional, Any
from pathlib import Path

from autoammonia.db.db_functions import add_valid_electrolytes_and_metals_to_db
from .utils.decorators import with_lock
from .config.config import DEFAULT_CONFIG, CONNECTIONS_INFO
from .utils.redis_client import client, client_initialization
from .reaction_steps import initialize_pump, restore_pump, execute_experiment


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
                             initialize_pumps: Optional[bool] = False,
                             restore_pumps: Optional[bool] = False,
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
    config = {**DEFAULT_CONFIG, **kwargs}
    config['delete_previous_queue'] = True if config['delete_previous_queue'].lower() == "true" else False
    delete_previous_queue = delete_previous_queue if delete_previous_queue is not None else config[
        'delete_previous_queue']
    parallel_cells = parallel_cells if parallel_cells is not None else config['parallel_cells']

    if delete_previous_queue:
        client.delete("experiment_queue")
    client_initialization(**kwargs)
    
    syringe_pumps = []
    for pump in CONNECTIONS_INFO:
        if 'tecan' in pump:
            syringe_pumps.append(pump)
    
    if initialize_pumps:
        for pump in syringe_pumps:
            initialize_pump(syringe_pump=pump, **kwargs)

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
            precursors, electrolytes = [],[]
            for exp in experiments:
                precursors += [exp['composition']]
                electrolytes += [exp['electrolyte']]
            add_valid_electrolytes_and_metals_to_db()
            execute_experiment(precursors, electrolytes, **kwargs)
    finally:
        if restore_pumps:
            for pump in syringe_pumps:
                restore_pump(syringe_pump=pump, **kwargs)
            logger.info("Flow stopped. All syringe pumps restored to their default state.")
        else:
            logger.info("Flow stopped.")

def reaction_module_deploy():
    process_experiment_queue.from_source(
        source=Path(__file__).parent,
        entrypoint=f"reaction_module.py:process_experiment_queue",
    ).deploy(
        name="reaction_module_flow",
        work_pool_name="reaction_module_pool",
    )
