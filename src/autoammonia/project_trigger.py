import asyncio
from prefect.client.orchestration import get_client

from .project_deploy import flows_to_deploy

async def trigger_workflow(flow_name, parameters):
    async with get_client() as client:
        print(f"🚀 Checking for active runs of '{flow_name}'...")

        deployment = await client.read_deployment_by_name(flow_name)
        if not deployment:
            print(f"❌ Deployment '{flow_name}' not found!")
            return

        # Check if there is an active run
        print(deployment)
        flow_runs = await client.read_flow_runs(deployment_filter=deployment)
        running = any(fr.state.is_running() for fr in flow_runs)

        if running:
            print(f"⚠️  Workflow '{flow_name}' already has a running flow run. Skipping...")
            return

        print(f"🚀 Triggering workflow '{flow_name}'...")
        run = await client.create_flow_run_from_deployment(
            deployment_id=deployment.id,
            parameters=parameters,
        )
        print(f"✅ Workflow '{flow_name}' triggered! Run ID: {run.id}")

async def gather_workflows():
    tasks = [trigger_workflow(f"{func.replace('_', '-')}/{flow}", {"kwargs":{}}) for func, flow, pool in flows_to_deploy]
    await asyncio.gather(*tasks)
    
def main():
    """
    Main function to trigger all workflows defined in the project.
    """
    asyncio.run(gather_workflows())