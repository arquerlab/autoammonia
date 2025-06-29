from pathlib import Path
import socket
from typing import Any
import paramiko
from prefect import task, get_run_logger

from ..config.config import DEFAULT_CONFIG
from .redis_client import client

def get_default_folder(
    measurement_type: str,
    **kwargs: Any,
) -> Path:
    config = {**DEFAULT_CONFIG, **kwargs}
    hostname = socket.gethostname()

    # Check hostname to determine which path to use
    if hostname == config.get("main_hostname", ""):
        chosen_path = config.get("data_path", "").strip()
    else:
        chosen_path = config.get("data_path_non_host", "").strip()

    # If the chosen path is missing or empty, fallback to home
    if not chosen_path:
        base_path = Path.home() / "ammonia_data"
    else:
        base_path = Path(chosen_path)

    target_folder = base_path / measurement_type
    target_folder.mkdir(parents=True, exist_ok=True)

    return target_folder

@task
def transfer_file_scp(
        local_file: Path,
        remote_folder: Path,
        remote_user: str | None,
        remote_password: str | None,
        remote_host: str | None,
        remote_port: int = 22,
        **kwargs: Any,
):
    # SCP connection setup
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    config = {**DEFAULT_CONFIG, **kwargs}
    remote_password = remote_password if remote_password is not None else config["scp_password"] 
    remote_user = remote_user if remote_user is not None else config["scp_user"]
    remote_host = remote_host if remote_host is not None else client.get('main_hostname')

    logger = get_run_logger()
    try:
        ssh.connect(remote_host, port=remote_port, username=remote_user, password=remote_password)

        # SCP transfer
        sftp = ssh.open_sftp()
        remote_path = Path(remote_folder) / local_file.name
        sftp.put(local_file, str(remote_path))
        sftp.close()

        logger.info(f"File {local_file} successfully transferred to {remote_user}@{remote_host}:{remote_path}")
        return remote_path
    except Exception as e:
        logger.error(f"Error during SCP transfer to {remote_host}:{remote_folder} with password {remote_password}: {e}")
        raise
    finally:
        ssh.close()