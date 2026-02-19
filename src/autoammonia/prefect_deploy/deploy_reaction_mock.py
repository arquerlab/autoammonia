import os
import asyncio

# IMPORTANT: set mock env var BEFORE importing modules that load config
os.environ["AUTOAMMONIA_MOCK_CONFIG"] = "true"
os.environ.pop("AUTOAMMONIA_SIMULATION", None)

from .deploy_reaction import WORK_POOL_NAME  # noqa: E402
from ..reaction_module import reaction_module_deploy  # noqa: E402
from ..safety_module_peri import safety_module_deploy  # noqa: E402
from ..utils.prefect import create_work_pool_if_not_exists  # noqa: E402


def main() -> None:
    """
    Deploy the reaction and safety flows using mock hardware config.

    This sets AUTOAMMONIA_MOCK_CONFIG=true so that config and components
    use the mock defaults while keeping simulation mode disabled.
    """
    asyncio.run(create_work_pool_if_not_exists(WORK_POOL_NAME, pool_type="process"))
    reaction_module_deploy()
    safety_module_deploy()


if __name__ == "__main__":
    main()

