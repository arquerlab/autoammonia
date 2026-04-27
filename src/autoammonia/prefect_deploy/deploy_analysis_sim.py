import os
import asyncio

# IMPORTANT: set simulation env var BEFORE importing modules that load config
os.environ["AUTOAMMONIA_SIMULATION"] = "true"
os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)

from ..analysis_module import analysis_module_deploy  # noqa: E402
from ..utils.prefect import create_work_pool_if_not_exists  # noqa: E402

SIM_WORK_POOL_NAME = "analysis_module_pool_sim"
SIM_DEPLOYMENT_NAME = "analysis_module_flow_sim"
SIM_ENVIRONMENT = {
    "AUTOAMMONIA_SIMULATION": "true",
    "AUTOAMMONIA_MOCK_CONFIG": "false",
}


def main() -> None:
    """
    Deploy the analysis flow in simulation mode.

    This sets AUTOAMMONIA_SIMULATION=true so that config and components
    use the simulation defaults and mock hardware classes.
    """
    asyncio.run(create_work_pool_if_not_exists(SIM_WORK_POOL_NAME, pool_type="process"))
    analysis_module_deploy(
        deployment_name=SIM_DEPLOYMENT_NAME,
        work_pool_name=SIM_WORK_POOL_NAME,
        entrypoint="simulation_entrypoints.py:track_reaction",
        environment=SIM_ENVIRONMENT,
    )


if __name__ == "__main__":
    main()

