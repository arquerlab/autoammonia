from prefect import flow, task, get_run_logger
import json
import time
from typing import Dict, Optional, Any, List
from pathlib import Path

from .db.db_functions import add_valid_electrolytes_and_metals_to_db
from .utils.decorators import with_lock
from .config.config import DEFAULT_CONFIG, CONNECTIONS_INFO, IS_SIMULATION
from .utils.prefect_variables import initialize_prefect_variables
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
                             ignore_steps: Optional[List[str]] = [],
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
    delete_previous_queue = delete_previous_queue if delete_previous_queue is not None else config[
        'delete_previous_queue']
    parallel_cells = parallel_cells if parallel_cells is not None else config['parallel_cells']

    if delete_previous_queue:
        client.delete("experiment_queue")
    client_initialization(**kwargs)
    overwrite_prefect_variables = config.get("overwrite_prefect_variables", IS_SIMULATION)
    initialize_prefect_variables(overwrite=overwrite_prefect_variables)
    
    syringe_pumps = []
    for pump in CONNECTIONS_INFO:
        if 'tecan' in pump or 'runze' in pump or 'syringe' in pump:
            syringe_pumps.append(pump)
    
    if initialize_pumps:
        for pump in syringe_pumps:
            if 'RX' in pump:
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
            execute_experiment(precursors, electrolytes, ignore_steps=ignore_steps, **kwargs)
    finally:
        if restore_pumps:
            for pump in syringe_pumps:
                restore_pump(syringe_pump=pump, **kwargs)
            logger.info("Flow stopped. All syringe pumps restored to their default state.")
        else:
            logger.info("Flow stopped.")

def reaction_module_deploy(
    deployment_names: List[str] | str = ["reaction_module_flow", "execute_experiment_flow"],
    work_pool_name: str = "reaction_module_pool",
    entrypoints: List[str] | str = ["reaction_module.py:process_experiment_queue", "reaction_module.py:execute_experiment"],
    environment: Optional[dict[str, str]] = None,
) -> None:
    """
    Create a Prefect deployment for the reaction module flow.

    Args:
        deployment_name (str): Name of the deployment to register in Prefect.
            Defaults to "reaction_module_flow".
        work_pool_name (str): Work pool that will execute this deployment.
            Defaults to "reaction_module_pool".
        entrypoint (str): Module entrypoint for the deployed flow.
            Defaults to "reaction_module.py:process_experiment_queue".
        environment (Optional[dict[str, str]]): Environment variables to inject
            at run time in the worker process. Defaults to None.

    Returns:
        None: This function registers the deployment in Prefect.
    """
    if isinstance(deployment_names, str):
        deployment_names = [deployment_names]
    if isinstance(entrypoints, str):
        entrypoints = [entrypoints]
    deploy_kwargs: List[dict[str, Any]] = [{
        "name": deployment_name,
        "work_pool_name": work_pool_name,
        "parameters": {"kwargs": {}},
    } for deployment_name in deployment_names]
    if environment is not None:
        for deploy_kwargs_item in deploy_kwargs:
            deploy_kwargs_item["job_variables"] = {"env": environment}

    for entrypoint, deploy_kwargs_item in zip(entrypoints, deploy_kwargs):
        eval(entrypoint.split(':')[1]).from_source(
            source=Path(__file__).parent,
            entrypoint=entrypoint,
        ).deploy(**deploy_kwargs_item)

