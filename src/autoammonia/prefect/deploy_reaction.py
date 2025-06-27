import asyncio
from ..reaction_module import reaction_module_deploy
from ..safety_module_peri import safety_module_deploy
from ..utils.prefect import create_work_pool_if_not_exists

WORK_POOL_NAME = "reaction_module_pool"

def main():
    asyncio.run(create_work_pool_if_not_exists(WORK_POOL_NAME, pool_type="process"))
    reaction_module_deploy()
    safety_module_deploy()


if __name__ == "__main__":
    main()