import os
import pandas as pd
import matplotlib.pyplot as plt
from typing import List
from prefect import task, get_run_logger


@task
def get_ocp_potential(
    folder: str, 
    parallel_cells: int,
    experiment_ids: List[int], 
    filename_suffix: str | None = None
) -> float:
    """
    Get the OCP potential for a given experiment ID and cell.
    """
    logger = get_run_logger()
    potentials = []
    try:
        for cell, experiment_id in zip(range(1, parallel_cells + 1), experiment_ids):
            filename = f'{experiment_id}_cell{str(cell).zfill(2)}_method_OCP{f"_{filename_suffix}" if filename_suffix is not None else ""}.csv'
            path = os.path.join(folder, filename)
            df = pd.read_csv(path)
            potentials.append(df['Potential (V)'].iloc[:10].mean())
            return potentials
    except Exception as e:
        logger.error(f"Error getting OCP potential: {e}")
        return [0 for _ in range(parallel_cells)]
