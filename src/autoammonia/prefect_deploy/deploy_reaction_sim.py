import os
import asyncio

# IMPORTANT: set simulation env var BEFORE importing modules that load config
os.environ["AUTOAMMONIA_SIMULATION"] = "true"
os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)

from ..reaction_module import reaction_module_deploy  
from ..safety_module_peri import safety_module_deploy  
from ..utils.prefect import create_work_pool_if_not_exists  

SIM_WORK_POOL_NAME = "reaction_module_pool_sim"
SIM_REACTION_DEPLOYMENT_NAME = "reaction_module_flow_sim"
SIM_SAFETY_DEPLOYMENT_NAME = "safety_module_flow_sim"
SIM_ENVIRONMENT = {
    "AUTOAMMONIA_SIMULATION": "true",
    "AUTOAMMONIA_MOCK_CONFIG": "false",
}


def main() -> None:
    """
    Deploy the reaction and safety flows in simulation mode.

    This sets AUTOAMMONIA_SIMULATION=true so that config and components
    use the simulation defaults and mock hardware classes.
    """
    asyncio.run(create_work_pool_if_not_exists(SIM_WORK_POOL_NAME, pool_type="process"))
    reaction_module_deploy(
        deployment_names=SIM_REACTION_DEPLOYMENT_NAME,
        work_pool_name=SIM_WORK_POOL_NAME,
        entrypoints="simulation_entrypoints.py:process_experiment_queue",
        environment=SIM_ENVIRONMENT,
    )

    safety_module_deploy(
        deployment_name=SIM_SAFETY_DEPLOYMENT_NAME,
        work_pool_name=SIM_WORK_POOL_NAME,
        entrypoint="simulation_entrypoints.py:track_safety",
        environment=SIM_ENVIRONMENT,
    )


if __name__ == "__main__":
    main()

