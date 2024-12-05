from prefect import flow, serve

from analysis_module import track_reaction
from reaction_module import process_experiment_queue
from peristaltic_safety_module import track_safety


@flow
def main()->None:
    analysis_flow = track_reaction.to_deployment(name='analysis_flow')
    reaction_flow = process_experiment_queue.to_deployment(name='reaction_flow')
    safety_flow = track_safety.to_deployment(name='safety_flow')
    serve(analysis_flow,reaction_flow,safety_flow)

if __name__ == '__main__':
    main()