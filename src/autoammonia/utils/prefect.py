from typing import List, Callable

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate

def create_deployments(flows: List[Callable]):
    return [flow.to_deployment(name=f"{flow.__name__}_deployment") for flow in flows]

async def create_work_pool_if_not_exists(pool_name: str, pool_type: str = "process"):
    """Creates a work pool if it doesn't already exist."""
    print(f"🔄 Checking or creating work pool: {pool_name} (type: {pool_type})")
    async with get_client() as client:
        existing = await client.read_work_pools()
        if pool_name not in [wp.name for wp in existing]:
            await client.create_work_pool(
                work_pool=WorkPoolCreate(
                    name=pool_name,
                    type=pool_type,
                    base_job_template={},  # Empty template for process pools
                )
            )
            print(f"✅ Created work pool: {pool_name}")
        else:
            print(f"ℹ️ Work pool already exists: {pool_name}")