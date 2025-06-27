from prefect import serve
from ..analysis_module import track_reaction, measure_vial
from ..utils.prefect import create_deployments

def main():
    deployments = create_deployments([track_reaction,measure_vial,])
    serve(*deployments)