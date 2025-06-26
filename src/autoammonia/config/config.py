import toml
from pathlib import Path

# Load default configuration
DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_config.toml"
DEFAULT_CONFIG = toml.load(DEFAULT_CONFIG_PATH)
if DEFAULT_CONFIG.get("simulation", False):
    DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_config_mock.toml"
    DEFAULT_CONFIG = toml.load(DEFAULT_CONFIG_PATH)

# Load connections info and setups
CONNECTIONS_INFO_PATH = Path(__file__).parent / "connections_info.toml"
_connections_data = toml.load(CONNECTIONS_INFO_PATH)
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

# Extract setups (e.g., config_setup_1)
CONFIG_SETUP_1 = _connections_data.get("setup", {}).get("config_setup_1", [])
