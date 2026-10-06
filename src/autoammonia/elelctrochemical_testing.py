import json
from prefect import flow, task
from typing import List, Any, Tuple
from pathlib import Path
from autoammonia.reaction_steps import execute_experiment

from autoammonia.utils.redis_client import client
from autoammonia.reaction_module import fetch_task_from_redis

def fetch_experiment_from_queue() -> dict:
    """
    Fetch the experiment from the experiment queue.
    """
    return fetch_task_from_redis("experiment_queue")


def _as_ratio_tuples(ratios: list[list[Any]]) -> list[Tuple[str, float]]:
    """
    Convert JSON-loaded ratio lists into tuples expected by `execute_experiment`.

    Args:
        ratios (list[list[Any]]): JSON-compatible ratio pairs.

    Returns:
        list[Tuple[str, float]]: Ratio pairs as tuples.
    """
    return [(str(name), float(value)) for name, value in ratios]


def _execute_queued_experiment(ignore_steps: list[str]) -> None:
    """
    Fetch one queued experiment and execute it with the batched shape expected by Prefect.

    Args:
        ignore_steps (list[str]): Workflow steps to skip.
    """
    experiment = fetch_experiment_from_queue()
    metal_ratios_list = [_as_ratio_tuples(experiment["composition"])]
    elyte_ratios_list = [_as_ratio_tuples(experiment["electrolyte"])]
    execute_experiment(
        metal_ratios_list,
        elyte_ratios_list,
        ignore_steps=ignore_steps,
    )


def delete_experiment_queue() -> None:
    """
    Delete the experiment queue.
    """
    client.delete("experiment_queue")


@flow
def execute_experiment_electrodeposition() -> None:
    """
    Execute the electrodeposition experiment.
    """
    _execute_queued_experiment(ignore_steps=['electrosynthesis', 'electrodissolution'])

@flow
def execute_experiment_characterization() -> None:
    """
    Execute the characterization experiment.
    """
    _execute_queued_experiment(
        ignore_steps=[
            'electrodeposition',
            'electrodissolution',
            'electrosynthesis_reaction',
            'electrosynthesis_characterization_prerx',
            "electrosynthesis_preparation",
            "electrosynthesis_wash",
        ]
    )

@flow
def execute_experiment_reaction() -> None:
    """
    Execute the reaction experiment.
    """
    _execute_queued_experiment(
        ignore_steps=[
            'electrodeposition',
            'electrodissolution',
            "electrosynthesis_preparation",
            'electrosynthesis_wash',
            'electrosynthesis_characterization_prerx',
            'electrosynthesis_characterization_postrx',
        ]
    )

@flow
def execute_experiment_electrosynthesis_preparation() -> None:
    """
    Execute the electrosynthesis preparation experiment.
    """
    _execute_queued_experiment(
        ignore_steps=[
            'electrodeposition',
            'electrodissolution',
            'electrosynthesis_reaction',
            'electrosynthesis_characterization_prerx',
            'electrosynthesis_characterization_postrx',
            'electrosynthesis_wash',
        ]
    )

@flow
def execute_experiment_electrosynthesis_wash() -> None:
    """
    Execute the electrosynthesis wash experiment.
    """
    _execute_queued_experiment(
        ignore_steps=[
            'electrodeposition',
            'electrodissolution',
            'electrosynthesis_reaction',
            'electrosynthesis_characterization_prerx',
            'electrosynthesis_characterization_postrx',
            'electrosynthesis_preparation',
        ]
    )

@flow
def execute_experiment_electrosynthesis() -> None:
    """
    Execute the electrosynthesis experiment.
    """
    _execute_queued_experiment(ignore_steps=['electrodeposition', 'electrodissolution'])

@flow
def execute_experiment_electrodissolution() -> None:
    """
    Execute the electrodissolution experiment.
    """
    _execute_queued_experiment(
        ignore_steps=['electrodeposition', 'electrosynthesis']
    )


def deploy_all(
    work_pool_name: str = "reaction_module_pool",
    ) -> None:
    """
    Create a Prefect deployment for the electrochemical testing flow.

    Args:
        work_pool_name (str): Work pool that will execute this deployment.
            Defaults to "reaction_module_pool".

    Returns:
        None: This function registers the deployment in Prefect.
    """
    deployment_names = ["TESTING_electrodeposition", "TESTING_characterization", 
    "TESTING_reaction", "TESTING_electrosynthesis_preparation", 
    "TESTING_electrosynthesis_wash", "TESTING_electrosynthesis", "TESTING_electrodissolution"]
    entrypoints = ["elelctrochemical_testing.py:execute_experiment_electrodeposition", 
    "elelctrochemical_testing.py:execute_experiment_characterization", 
    "elelctrochemical_testing.py:execute_experiment_reaction", 
    "elelctrochemical_testing.py:execute_experiment_electrosynthesis_preparation", 
    "elelctrochemical_testing.py:execute_experiment_electrosynthesis_wash", 
    "elelctrochemical_testing.py:execute_experiment_electrosynthesis", 
    "elelctrochemical_testing.py:execute_experiment_electrodissolution"]
    deploy_kwargs: List[dict[str, Any]] = [{
        "name": deployment_name,
        "work_pool_name": work_pool_name,
    } for deployment_name in deployment_names]

    for entrypoint, deploy_kwargs_item in zip(entrypoints, deploy_kwargs):
        function_name = entrypoint.split(':')[1]
        resolved_object = eval(function_name)
        resolved_object.from_source(
            source=Path(__file__).parent,
            entrypoint=entrypoint,
        ).deploy(**deploy_kwargs_item)

if __name__ == "__main__":
    client.delete("experiment_queue")
    deploy_all()
