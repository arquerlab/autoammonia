import os.path
from typing import Any
import paramiko
from pathlib import Path


from prefect import flow, task

from ..utils.decorators import run_on_component_with_lock
from ..config.config import DEFAULT_CONFIG

import pandas as pd

@run_on_component_with_lock
@flow
def measure_spectrum(
        spectrometer: object,
        integration_time: float,
        experiment_id: str,
        vial_id: str,
        **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    non_adrastea_data_path = Path(config['non_adrastea_data_path']) / 'uv_vis'
    adrastea_data_path = Path(config['adrastea_data_path']) / 'uv_vis'
    
    # Measure the spectrum
    wavelength = spectrometer.wavelength
    data = spectrometer.measure_spectrum(integration_time)

    # Create a DataFrame
    df = pd.DataFrame({
        "Wavelength (nm)": wavelength,
        "Intensity": data
    })
    
    if not os.path.exists(non_adrastea_data_path):
        os.mkdir(non_adrastea_data_path)
    filename = non_adrastea_data_path / f"experiment_{experiment_id}_vial_{vial_id}.csv"
    df.to_csv(filename, index=False)
    transfer_file_scp(filename, adrastea_data_path, 'poten', 'adrastea')

@task
def transfer_file_scp(
        local_file: Path,
        remote_path: Path,
        remote_user: str,
        remote_host: str,
        remote_port: int = 22,
):
    # SCP connection setup
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Replace with your credentials
    password = os.getenv("poten", "potato12")  # Use environment variables for security

    try:
        ssh.connect(remote_host, port=remote_port, username=remote_user, password=password)

        # SCP transfer
        sftp = ssh.open_sftp()
        sftp.put(local_file, str(remote_path))
        sftp.close()

        print(f"File {local_file} successfully transferred to {remote_user}@{remote_host}:{remote_path}")
    except Exception as e:
        print(f"Error during SCP transfer: {e}")
    finally:
        ssh.close()
