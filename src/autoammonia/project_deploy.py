import asyncio
import socket
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.filesystems import LocalFileSystem
from pathlib import Path

from .analysis_module import track_reaction, analysis_module_deploy
from .reaction_module import process_experiment_queue, reaction_module_deploy
from .safety_module_peri import track_safety, safety_module_deploy

flows_to_deploy = [
        ("track_reaction", "analysis_module_flow", "analysis_module_pool",),
        ("process_experiment_queue", "reaction_module_flow", "reaction_module_pool",),
        ("track_safety", "safety_module_flow", "reaction_module_pool",),
    ]

def main():
    hostname = socket.gethostname()

    async def create_work_pool_if_not_exists(pool_name: str):
        print(f"🔄 Checking or creating work pool: {pool_name}")
        async with get_client() as client:
            existing = await client.read_work_pools()
            if pool_name not in [wp.name for wp in existing]:
                await client.create_work_pool(
                    work_pool=WorkPoolCreate(
                        name=pool_name,
                        type="process",
                        base_job_template={},
                    )
                )
                print(f"✅ Created work pool: {pool_name}")
            else:
                print(f"ℹ️ Work pool already exists: {pool_name}")
    async def create_all_work_pools():
        for _, _, pool in flows_to_deploy:
            await create_work_pool_if_not_exists(pool)

    def deploy_flows():
        analysis_module_deploy()
        reaction_module_deploy()
        safety_module_deploy()

    def print_computer_instructions(main_hostname):
        print("\n🖥️  For setting the workers responsible of executing the workflows:")
        print("Run the following command:\n")
        print(f"   export PREFECT_API_URL=http://{main_hostname}:4200/api")
        print("   prefect worker start -p reaction_module_pool\n"
              "And then in another terminal/computer:\n"
              "   export PREFECT_API_URL=http://{main_hostname}:4200/api"
              "   prefect worker start-p analysis_module_pool\n")


            
    # Run all steps
    asyncio.run(create_all_work_pools())
    deploy_flows()
    print_computer_instructions(hostname)
