import asyncio
from prefect.client.orchestration import get_client

# Define the list of workflows to trigger
workflows_to_trigger = [
    {"flow_name": "analysis_flow", "parameters": {}},
    {"flow_name": "reaction_flow", "parameters": {}},
    {"flow_name": "safety_flow", "parameters": {}},
]

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
    tasks = [trigger_workflow(workflow["flow_name"], workflow["parameters"]) for workflow in workflows_to_trigger]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())