from prefect import serve
from ..analysis_module import track_reaction
from ..utils.prefect import create_deployments

def main():
    deployments = create_deployments([track_reaction,])
    serve(*deployments)