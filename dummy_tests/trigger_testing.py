from prefect.deployments import run_deployment
import asyncio
from typing import List

async def trigger_deployments_async(deployment_list: List[dict]):
    for deployment in deployment_list:
        # Full name format: <flow_function_name>/<deployment_name>
        run = await run_deployment(
            name=f"{deployment['flow_name']}/{deployment['name']}",
            timeout=0
        )
        print(f"Triggered {deployment['name']} with run ID: {run.id}")

def trigger_deployments(deployments: List[dict]):
    asyncio.run(trigger_deployments_async(deployments))

print('test')
