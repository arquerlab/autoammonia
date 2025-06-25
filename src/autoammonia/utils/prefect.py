import threading
import time
import asyncio
from typing import List, Callable
from prefect import serve
from prefect.deployments import run_deployment

def create_deployments(flows: List[Callable]):
    return [flow.to_deployment(name=f"{flow.__name__}_deployment") for flow in flows]