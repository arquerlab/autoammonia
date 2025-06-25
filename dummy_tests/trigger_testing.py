# trigger_flows.py
from prefect import flow
from prefect.deployments import run_deployment
import asyncio

async def trigger():
    print("🚀 Starting orchestration flow to trigger deployments.")

    # Trigger main0_deployment
    print("\n--- Triggering 'main0-flow/main0-deployment' ---")
    # Full name format: <flow_function_name>/<deployment_name>
    main0_run = await run_deployment(
        name="main0/main0_deployment",
        timeout=0
    )
    print(f"Triggered reaction module with run ID: {main0_run.id}")

    # Trigger main1_deployment
    print("\n--- Triggering 'main1-flow/main1-deployment' ---")
    main1_run = await run_deployment(
        name="main1/main1_deployment",
        timeout=0
    )
    print(f"Triggered safety module with run ID: {main1_run.id}")

    print("\n🏁 Orchestration flow finished triggering deployments.")

def main():
    asyncio.run(trigger())
    
if __name__ == "__main__":
    main()
