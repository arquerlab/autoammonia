import os

# Set simulation mode before importing any module that reads config.
os.environ["AUTOAMMONIA_SIMULATION"] = "true"
os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)

from .analysis_module import track_reaction  # noqa: E402
from .reaction_module import process_experiment_queue  # noqa: E402
from .safety_module_peri import track_safety  # noqa: E402

