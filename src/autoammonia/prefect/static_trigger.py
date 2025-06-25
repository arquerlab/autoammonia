from prefect.deployments import run_deployment
import asyncio
from typing import List

deployments_to_trigger = [
    {
        "flow_name": "process_experiment_queue",
        "name": "process-experiment-queue-deployment"
    },
    {
        "flow_name": "track_safety",
        "name": "track-safety-deployment"
    },
    {
        "flow_name": "track_reaction",
        "name": "track-reaction-deployment"
    }
]

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
    
def main():
    """
    Main function to trigger all deployments defined in the list.
    """
    print("Starting deployment triggers...")
    trigger_deployments(deployments_to_trigger)
    print("All deployments triggered.")