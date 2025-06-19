from prefect.client import get_client
from datetime import datetime
import asyncio

async def trigger_deployment():
    async with get_client() as client:
        # Create a flow run
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id="example_flow/example-deployment",
            name=f"Manual trigger by adpisa at 2025-06-18 18:01:31"
        )
        print(f"Created flow run {flow_run.id}")
        return flow_run.id

if __name__ == "__main__":
    asyncio.run(trigger_deployment())