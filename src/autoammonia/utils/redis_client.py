import redis
import socket

from ..config.config import DEFAULT_CONFIG, HOSTNAME

# Module-level cache for the Redis client (lazy initialization)
_cached_client = None

def create_redis_client()-> redis.Redis:
        """
        Dynamically creates a Redis client based on the hostname of the machine.
        
        This function selects the appropriate Redis connection configuration
        based on the machine's hostname. If the hostname is "localhost", it uses
        the configuration for the local Redis instance. Otherwise, it defaults to the
        fallback host "adrastea".
        
        Returns:
            redis.Redis: An initialized Redis client connected to the appropriate host.
        
        Raises:
            redis.ConnectionError: If the connection to Redis fails for both configurations.
        """
        # Connection configurations
        configs = {
                "localhost": {"host": "localhost", "port": 6379, "password": "potato12"},
                "adrastea": {"host": "adrastea", "port": 6379, "password": "potato12"}
        }

        # Dynamically select the configuration based on hostname.
        # On your PC (hostname like 'pc1836'), fall back to localhost.
        selected_config = configs.get(HOSTNAME, configs["localhost"])
        redis_client = redis.StrictRedis(
                host=selected_config["host"],
                port=selected_config["port"],
                password=selected_config["password"],
                decode_responses=True
                )
        redis_client.ping()
        return redis_client


def get_client()->redis.Redis:
        """
        Get Redis client, creating it only when first needed.
        
        Returns:
                redis.Redis: The Redis client.
        """
        global _cached_client
        if _cached_client is None:
                _cached_client = create_redis_client()
        return _cached_client

class _ClientProxy:
        """Proxy class to delegate attribute access to the Redis client."""
        def __getattr__(self, name):
                """Delegate attribute access to the Redis client."""
                real_client = get_client()
                import sys
                sys.modules[__name__]._cached_client = real_client
                return getattr(real_client, name)

client = _ClientProxy()

def client_initialization(**kwargs)->None:
        """Initialization of redis server, resetting all variables to the initial stage"""

        config = {**DEFAULT_CONFIG,**kwargs}
        parallel_cells = config['parallel_cells']

        # Variables to track filled and empty vials
        client.rpush('empty_vials', *['vial1', 'vial2', 'vial3', 'vial4', 'vial5', 'vial6', 'vial7', 'vial8'])
        client.delete('filled_vials')
        
        for cell in range(1,parallel_cells+1):
                cell_str = str(cell).zfill(2)
                # Variables to track volume on each compartment
                client.set(f'WEvial{cell_str}_volume', 0)
                client.set(f'CEvial{cell_str}_volume', 0)
                # Variables to track reaction status on eacch cell
                client.set(f'flowcell{cell_str}_reaction_catholyte','')
                client.set(f'flowcell{cell_str}_reaction_metal_ratios','')

        # Variables to track reaction status and safety
        client.set('reaction_status', 'waiting')
        client.set('flow_cell_content', 'clean')
        client.set('safety_operation', 1)
        # Variables to track pump status
        client.set('longerWE01', '0')
        client.set('longerCE01', '0')
