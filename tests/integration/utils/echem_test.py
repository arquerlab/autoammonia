from pathlib import Path
import pandas as pd

from autoammonia.utils.echem import get_ocp_potential


def test_get_ocp_potential(tmp_path: Path) -> None:
    """
    Very simple test to check that get_ocp_potential reads a CSV and computes the mean.
    """
    folder = tmp_path
    experiment_id = 1
    filename = f"{experiment_id}_cell01_method_OCP.csv"

    # Create a minimal CSV with known values
    df = pd.DataFrame({"Potential (V)": [0.0, 0.5, 1.0]})
    df.to_csv(folder / filename, index=False)

    result = get_ocp_potential(str(folder), parallel_cells=1, experiment_id=experiment_id)

    # Mean of [0.0, 0.5, 1.0] is 0.5
    assert result[0] == 0.5

