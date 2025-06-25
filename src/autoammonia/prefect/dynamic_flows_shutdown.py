import asyncio
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterState, WorkPoolFilter, WorkPoolFilterName
from prefect.states import Cancelled

from .dynamic_deploy import flows_to_deploy

async def cancel_flows_in_workpool(pool_name: str):
    print(f"🔍 Looking for active flows in work pool: '{pool_name}'")
    async with get_client() as client:
        flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(type={"any_": ["RUNNING"]})
            ),
            work_pool_filter=WorkPoolFilter(
                name=WorkPoolFilterName(any_=[pool_name])
            ),
            limit=100
        )

        if not flow_runs:
            print(f"✅ No running flows in '{pool_name}'.")
            return

        for run in flow_runs:
            print(f"🛑 Cancelling flow run: {run.id} ({run.name})")
            await client.set_flow_run_state(run.id, Cancelled())

        print(f"✅ Cancelled {len(flow_runs)} running flow(s) in '{pool_name}'.")

async def cancel_all_flows():
    work_pools = {pool for _, _, pool in flows_to_deploy}
    for pool in work_pools:
        await cancel_flows_in_workpool(pool)

def main():
    """
    Entry point to cancel all running flows in work pools defined in flows_to_deploy.
    """
    asyncio.run(cancel_all_flows())