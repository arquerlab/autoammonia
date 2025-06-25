from prefect import serve
from ..reaction_module import process_experiment_queue
from ..safety_module_peri import track_safety
from ..utils.prefect import create_deployments

def main():
    deployments = create_deployments([process_experiment_queue,track_safety])
    serve(*deployments)