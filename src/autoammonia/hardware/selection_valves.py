from typing import Optional, Any
from prefect import task, get_run_logger

from ..utils.redis_client import client
from ..utils.decorators import run_on_component
from ..config.config import DEFAULT_CONFIG, CONNECTIONS_INFO


@task
def switch_port_valve(
        valve: str,
        port: str,
        retries: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Attempts to switch the specified valve to a different port, 
    retrying the operation if it fails according to the provided retry configuration.
    
    This function wraps the pump operation with a lock mechanism, ensuring that the pump 
    resource is accessed in a thread-safe manner. If the operation fails after the retries, 
    a `RuntimeError` is raised and the flag 'safety_operation' is set to 0 in redis, which
    will trigger the emergency_stop function.

    Args:
        valve (str): The valve to operate.
        port (str): Identifier of the valve port to switch to.
        retries (Optional[int], default=None): The number of times to retry the operation if it fails.
            Defaults to config['valve_retries'].
        **kwargs (Any): Additional configuration options.

    Raises:
        RuntimeError: If the valve operation fails after the specified number of retries.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['valve_retries']
    logger = get_run_logger()

    @task
    @run_on_component()
    def switch_port_func(
            valve: str,
            port: str,
    ) -> None:
        """
        Switches the specified valve to a different port.

        Args:
            valve (str): The valve to operate.
            port (str): Identifier of the valve port to switch to.
        """
        valve.switch_port(port)
        
    try:
        switch_port_func.with_options(retries=retries)(valve, port)
    except Exception as e:
        client.set('safety_operation',0)
        logger.error((f"Failed to switch valve '{valve}' to port '{port}' after {retries} retries."))
        logger.error(f"Available ports in {valve}: {CONNECTIONS_INFO[valve]}")
        raise