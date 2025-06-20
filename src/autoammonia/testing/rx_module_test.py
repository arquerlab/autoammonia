from ..reaction_module import process_experiment_queue

if __name__ == '__main__':
    """
    This script is designed to run the reaction module flow, processing tasks from the experiment queue.
    It can be executed directly to start the flow.
    """
    process_experiment_queue(delete_previous_queue=True,
                             electrodeposition_time=600, reaction_time=10, electrodisolution_time=10,
                             electrodeposition_current=-0.004, reaction_current=+0.004,
                             wash_flow_cell_repeats=1, wash_flow_cell_wash_comp_volume=2.5,
                             )