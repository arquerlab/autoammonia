import asyncio
from prefect.client.orchestration import get_client

from .project_deploy import flows_to_deploy

async def trigger_workflow(flow_name, parameters):
    async with get_client() as client:
        print(f"🚀 Triggering workflow '{flow_name}'...")
        deployment = await client.read_deployment_by_flow_name(flow_name)
        if deployment:
            run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters=parameters,
            )
            print(f"✅ Workflow '{flow_name}' triggered! Run ID: {run.id}")
        else:
            print(f"❌ Workflow '{flow_name}' not found!")

async def main():
    tasks = [trigger_workflow(workflow["flow_name"], workflow["parameters"]) for workflow in flows_to_deploy]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())