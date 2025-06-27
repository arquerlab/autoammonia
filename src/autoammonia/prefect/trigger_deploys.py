from prefect.deployments import run_deployment
import asyncio
from typing import List

deployments_to_trigger = [
    "process-experiment-queue/process_experiment_queue_flow",
    "track-safety/track_safety_flow",
    "track-reaction/track_reaction_flow",
]


async def trigger_deployments_async(deployment_list: List[str]):
    for deployment in deployment_list:
        print(f"🔄 Triggering deployment: {deployment})")
        # Full name format: <flow_function_name>/<deployment_name>
        run = await run_deployment(
            name=f"{deployment}",
            timeout=0,
            parameters={'kwargs': {}},
        )
        print(f"Triggered {deployment} with run ID: {run.id}")


def trigger_deployments(deployments: List[str]):
    asyncio.run(trigger_deployments_async(deployments))


def main():
    """
    Main function to trigger all deployments defined in the list.
    """
    print("Starting deployment triggers...")
    trigger_deployments(deployments_to_trigger)
    print("All deployments triggered.")