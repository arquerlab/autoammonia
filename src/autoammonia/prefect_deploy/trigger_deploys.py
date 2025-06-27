from ..utils.prefect import trigger_deployments

deployments_to_trigger = [
    "process-experiment-queue/reaction_module_flow",
    "track-safety/safety_module_flow",
    "track-reaction/analysis_module_flow",
]


def main():
    """
    Main function to trigger all deployments defined in the list.
    """
    print("Starting deployment triggers...")
    trigger_deployments(deployments_to_trigger)
    print("All deployments triggered.")