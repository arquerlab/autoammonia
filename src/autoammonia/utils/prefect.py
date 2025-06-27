from datetime import datetime
from typing import List
import asyncio
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.deployments import run_deployment

def create_deployments(flows: List[flow]):
    return [flow_to_deploy.to_deployment(name=f"{flow_to_deploy.__name__}_deployment") for flow_to_deploy in flows]

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
            
async def trigger_deployments_async(
        deployment_list: List[str],
        scheduled_time: datetime | None,
        parameters: dict | None = None
) -> None:
    for deployment in deployment_list:
        print(f"🔄 Triggering deployment: {deployment})")
        # Full name format: <flow_function_name>/<deployment_name>
        if parameters:
            parameters = {'kwargs': {]}
        else:
            if 'kwargs' not in parameters:
                parameters = {'kwargs': {}}
        run = await run_deployment(
            name=f"{deployment}",
            timeout=0,
            parameters=parameters,
            scheduled_time = scheduled_time,
        )
        print(f"Triggered {deployment} with run ID: {run.id}")


def trigger_deployments(
        deployments: List[str], 
        scheduled_time: datetime | None = None, 
        parameters: dict | None = None
) -> None:
    asyncio.run(trigger_deployments_async(deployment_list=deployments, scheduled_time= scheduled_time, 
                                          parameters= parameters))
    