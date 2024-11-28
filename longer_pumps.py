from typing import Optional, Any
from prefect import task

from redis_client import client
from decorators import run_on_component_with_lock
from default_config import DEFAULT_CONFIG


@task
def run_pump(
        pump: str,
        speed: float,
        direction: Optional[bool] = None,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        acquisition_timeout: Optional[int] = None,
        function_timeout: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Attempts to activate the specified pump with the given speed and direction, 
    retrying if the operation fails according to the provided retry configuration.

    This function wraps the pump operation with a lock mechanism, ensuring that the pump 
    resource is accessed in a thread-safe manner. If the operation fails after the retries, 
    a `RuntimeError` is raised and the flag 'safety_operation' is set to 0 in redis, which
    will trigger the emergency_stop function.

    Args:
        pump (str): The name or identifier of the pump.
        speed (float): The speed at which to run the pump (in rpm).
        direction (Optional[bool], default=None): Direction of the pump's rotation. 
            False for clockwise, True for counterclockwise. If None, the default direction is used.
        retries (Optional[int]): The number of times to retry the operation if it fails.
            Defaults to `config['longer_retries']`.
        retries_delay (Optional[float]): The delay (in seconds) between retry attempts.
            Defaults to `config['longer_retries_delay']`.
        acquisition_timeout (Optional[int]): Maximum time (in seconds) to wait for acquiring the lock.
            Defaults to `config['longer_acq_timeout']`.
        function_timeout (Optional[int]): Maximum time (in seconds) allowed for the pump operation to complete.
            Defaults to `config['longer_func_timeout']`.
        **kwargs (Any): Additional configuration options to override the defaults.

    Raises:
        RuntimeError: If the pump operation fails after the specified number of retries.
    """
    # Load default configurations and apply overrides
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries_delay']
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['longer_acq_timeout']
    function_timeout = function_timeout if function_timeout is not None else config['longer_func_timeout']

    # Define the pump operation function with the lock decorator
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout=function_timeout)
    def run_pump_func(
            pump: str,
            speed: float,
            direction: Optional[bool] = None
    ) -> None:
        """
        Activates the specified pump with the given speed and direction.

        Args:
            pump (str): The name or identifier of the pump.
            speed (float): The speed at which to run the pump (in rpm).
            direction (Optional[bool], default=None): Direction of the pump's rotation.
                False for clockwise, True for counterclockwise. If None, the default direction is used.
        """
        pump.run(speed, direction)
        direction_sign = +1 if direction else -1
        client.set(str(pump), speed * direction_sign)

    # Execute the wrapped function with retries
    try:
        run_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay
                                   )(pump=pump, speed=speed, direction=direction)
    except Exception as e:
        client.set('safety_operation', 0)
        raise RuntimeError(f"Failed to run pump '{pump}' after {retries} retries.") from e


@task
def stop_pump(
        pump: str,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        acquisition_timeout: Optional[int] = None,
        function_timeout: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Attempts to stop the specified pump, retrying if the operation fails 
    according to the provided retry configuration.
    
    This function wraps the pump operation with a lock mechanism, ensuring that the pump 
    resource is accessed in a thread-safe manner. If the operation fails after the retries, 
    a `RuntimeError` is raised and the flag 'safety_operation' is set to 0 in redis, which
    will trigger the emergency_stop function.
    
    Args:
        pump (str): The name or identifier of the pump.
        retries (Optional[int]): The number of times to retry the operation if it fails.
            Defaults to `config['longer_retries']`.
        retries_delay (Optional[float]): The delay (in seconds) between retry attempts.
            Defaults to `config['longer_retries_delay']`.
        acquisition_timeout (Optional[int]): Maximum time (in seconds) to wait for acquiring the lock.
            Defaults to `config['longer_acq_timeout']`.
        function_timeout (Optional[int]): Maximum time (in seconds) allowed for the pump operation to complete.
            Defaults to `config['longer_func_timeout']`.
        **kwargs (Any): Additional configuration options.

    Raises:
        RuntimeError: If the pump operation fails after the specified number of retries.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries']
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['longer_acq_timeout']
    function_timeout = function_timeout if function_timeout is not None else config['longer_func_timeout']

    # Define the pump operation function with the lock decorator
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout=function_timeout)
    def stop_pump_func(pump: str) -> None:
        """
        Stops the specified pump.

        Args:
            pump (str): The name or identifier of the pump to stop.
        """
        pump.stop()

    try:
        stop_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay)(pump)
    except Exception as e:
        client.set('safety_operation', 0)
        raise RuntimeError(f"Failed to stop pump '{pump}' after {retries} retries.") from e


@task
def check_pump(
        pump: str,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        acquisition_timeout: Optional[int] = None,
        function_timeout: Optional[int] = None,
        **kwargs: Any,
) -> float:
    """
    Attempts to check the status of the specified pump, retrying if the operation 
    fails according to the provided retry configuration.
    
    This function wraps the pump operation with a lock mechanism, ensuring that the pump 
    resource is accessed in a thread-safe manner. If the operation fails after the retries, 
    a `RuntimeError` is raised and the flag 'safety_operation' is set to 0 in redis, which
    will trigger the emergency_stop function.
    
    Args:
        pump (str): The name or identifier of the pump.
        retries (Optional[int]): The number of times to retry the operation if it fails.
            Defaults to `config['longer_retries']`.
        retries_delay (Optional[float]): The delay (in seconds) between retry attempts.
            Defaults to `config['longer_retries_delay']`.
        acquisition_timeout (Optional[int]): Maximum time (in seconds) to wait for acquiring the lock.
            Defaults to `config['longer_acq_timeout']`.
        function_timeout (Optional[int]): Maximum time (in seconds) allowed for the pump operation to complete.
            Defaults to `config['longer_func_timeout']`.
        **kwargs (Any): Additional configuration options.
    
    Returns:
        float: The current status of the pump: value indicates speed while the sign indicates direction 
        (+ for counterclockwise and - for clockwise).

    Raises:
        RuntimeError: If the pump operation fails after the specified number of retries.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries']
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config['longer_acq_timeout']
    function_timeout = function_timeout if function_timeout is not None else config['longer_func_timeout']

    # Define the pump operation function with the lock decorator
    @task
    @run_on_component_with_lock(acquisition_timeout=acquisition_timeout, function_timeout=function_timeout)
    def check_pump_func(pump: str) -> float:
        """
        Checks the current status of the specified pump.

        Args:
            pump (str): The name or identifier of the pump to check.

        Returns:
            float: The current status of the pump: value indicates speed while the sign indicates direction 
            (+ for counterclockwise and - for clockwise).
        """
        return pump.get_state()
    try:
        return check_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay)(pump)
    except Exception as e:
        client.set('safety_operation', 0)
        raise RuntimeError(f"Failed to check the status of pump '{pump}' after {retries} retries.") from e