from ..reaction_module import process_experiment_queue
from ..safety_module_peri import track_safety
from ..utils.prefect import create_deployments
from prefect.deployments import run_deployment
import asyncio
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate

def main():
    flows_to_deploy = [process_experiment_queue,track_safety]
    deployments = create_deployments(flows_to_deploy)
    async def create_work_pool_if_not_exists(pool_name: str):
        print(f"🔄 Checking or creating work pool: {pool_name}")
        async with get_client() as client:
            existing = await client.read_work_pools()
            if pool_name not in [wp.name for wp in existing]:
                await client.create_work_pool(
                    work_pool=WorkPoolCreate(
                        name=pool_name,
                        type="process",
                        base_job_template={},
                    )
                )
                print(f"✅ Created work pool: {pool_name}")
            else:
                print(f"ℹ️ Work pool already exists: {pool_name}")
    asyncio.run(create_work_pool_if_not_exists("reaction_module_pool"))
    for deploy in deployments:
        run_deployment(deploy)