import toml
import socket
import os
from pathlib import Path


def detect_setup() -> str:
    """
    Detect active setup based on hostname.

    Loads hostname mappings from setup_mappings.toml and checks the current
    hostname against the configured patterns. Can be overridden via
    AUTOAMMONIA_SETUP environment variable.

    Returns:
        str: The detected setup name (e.g., 'toronto' or 'barcelona').
    """
    # Allow override via environment variable
    env_setup = os.getenv("AUTOAMMONIA_SETUP")
    if env_setup:
        return env_setup.lower()

    # Load setup mappings from TOML file
    mappings_path = Path(__file__).parent / "setup_mappings.toml"
    mappings = toml.load(mappings_path)
    
    # Get current hostname (lowercase for case-insensitive matching)
    hostname = socket.gethostname().lower()
    
    # Check each setup's hostname patterns
    for setup_name, setup_config in mappings.items():
        if setup_name == "default":
            continue
        
        hostnames = setup_config.get("hostnames", [])
        for pattern in hostnames:
            if pattern.lower() in hostname:
                return setup_name
    
    # Return default setup if no match found
    default_setup = mappings.get("default", {}).get("setup", "toronto")
    return default_setup


# Detect active setup
ACTIVE_SETUP = detect_setup()

# Load default configuration using setup-specific file
DEFAULT_CONFIG_PATH = Path(__file__).parent / f"default_config_{ACTIVE_SETUP}.toml"
DEFAULT_CONFIG = toml.load(DEFAULT_CONFIG_PATH)

# Check if simulation mode is enabled
if DEFAULT_CONFIG.get("simulation", False):
    DEFAULT_CONFIG_MOCK_PATH = Path(__file__).parent / f"default_config_mock_{ACTIVE_SETUP}.toml"
    DEFAULT_CONFIG = toml.load(DEFAULT_CONFIG_MOCK_PATH)

# Load connections info and setups - use setup-specific file
CONNECTIONS_INFO_PATH = Path(__file__).parent / f"connections_info_{ACTIVE_SETUP}.toml"
_connections_data = toml.load(CONNECTIONS_INFO_PATH)

# Process connections info
for instrument in _connections_data:
    if instrument != "setup":
        for port in _connections_data[instrument]:
            _connections_data[instrument][port].setdefault('usage', None)

# Extract instrument connections, skipping the 'setup' section
CONNECTIONS_INFO = {
    instrument: {port: dict(info) for port, info in ports.items()}
    for instrument, ports in _connections_data.items()
    if instrument != "setup"
}

# Extract active setup component list
CONFIG_SETUP = _connections_data.get("setup", {}).get("components", [])
