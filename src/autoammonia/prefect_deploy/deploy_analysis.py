import asyncio

from autoammonia.analysis_module import analysis_module_deploy
from ..utils.prefect import create_work_pool_if_not_exists

WORK_POOL_NAME = "analysis_module_pool"

def main():
    asyncio.run(create_work_pool_if_not_exists(WORK_POOL_NAME, pool_type="process"))
    analysis_module_deploy()


if __name__ == "__main__":
    main()