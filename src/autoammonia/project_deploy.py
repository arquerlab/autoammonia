import asyncio
import socket
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from autoammonia.utils.redis_client import client as redis_client
from prefect.filesystems import RemoteFileSystem

from .analysis_module import track_reaction
from .reaction_module import process_experiment_queue
from .peristaltic_safety_module import track_safety

def main():
    hostname = socket.gethostname()
     #redis_client.set("main_hostname", hostname)

    flows_to_deploy = [
        (track_reaction, "analysis_flow", "analysis-pool"),
        (process_experiment_queue, "reaction_flow", "reaction-pool"),
        (track_safety, "safety_flow", "safety-pool"),
    ]

    async def create_work_pool_if_not_exists(pool_name: str):
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

    def deploy_flows():
        for flow_func, deployment_name, pool_name in flows_to_deploy:
            print(f"🚀 Deploying '{deployment_name}' to pool '{pool_name}'...")
            # Use the existing Redis client to store deployment metadata
            redis_client.hset(
                f"deployment:{deployment_name}",
                mapping={
                    "deployment_name": deployment_name,
                    "pool_name": pool_name,
                    "hostname": hostname,
                }
            )
            flow_func.deploy(
                name=deployment_name,
                work_pool_name=pool_name,
                storage=RemoteFileSystem(
                    basepath=f"redis://{redis_client.host}:{redis_client.port}/deployments",
                    password=redis_client.password  # Use your Redis client's existing password
                )  # Use Redis as storage
            )

    def print_computer_instructions(main_hostname):
        print("\n🖥️  If running all from a single computer:")
        print("Run the following command:\n")
        print(f"   export PREFECT_API_URL=http://{main_hostname}:4200/api")
        print("   prefect agent start -p safety-pool -p reaction-pool -p analysis-pool\n")

        print("🖥️  If running from different computers:")
        print("On MAIN computer:\n")
        print(f"   export PREFECT_API_URL=http://{main_hostname}:4200/api")
        print("   prefect agent start -p safety-pool -p reaction-pool\n")
        print("On SIDE computer:\n")
        print(f"   export PREFECT_API_URL=http://{main_hostname}:4200/api")
        print("   prefect agent start -p analysis-pool\n")

    # Run everything
    for _, _, pool in flows_to_deploy:
        asyncio.run(create_work_pool_if_not_exists(pool))

    deploy_flows()
    print_computer_instructions(hostname)
