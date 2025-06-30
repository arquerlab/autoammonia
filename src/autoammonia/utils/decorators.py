from typing import Optional, ParamSpec, Callable, Concatenate
from functools import wraps
import time

from prefect import get_run_logger
from redis.exceptions import LockError
import redis.lock

from ..utils.redis_client import client
from ..config.config import DEFAULT_CONFIG
from ..config.components_config import get_config_components
from ..utils.importing import resolve_class

_component_instances = {}

P = ParamSpec("P")

def acquire_lock(component_name:str, function_timeout: int, acquisition_timeout: int, function: Callable) -> redis.lock:
    lock_name = f'{component_name}_lock'
    ini_time = time.time()
    logger = get_run_logger()
    logger.info(f"[{component_name}] {function.__name__} is trying to acquire lock. Acq timeout: {acquisition_timeout}")
    lock = client.lock(lock_name, timeout=acquisition_timeout)
    if lock.acquire(blocking=True):
        acquisition_time = time.time() - ini_time
        logger.info(f"[{component_name}] {function.__name__} acquired the lock after waiting for {acquisition_time}s")
        lock.extend(additional_time=function_timeout + acquisition_time)
        logger.info(f"[{component_name}] {function.__name__} lock extended for function to execute: {function_timeout + acquisition_time}s")
        return lock
    else:
        logger.error(f"[{component_name}] {function.__name__} was not able to acquire the lock")
        raise LockError(f"Could not acquire lock for {component_name}. Another process is blocking it.")

def get_or_create_component_instance(component_name: str):
    logger = get_run_logger()
    if component_name not in _component_instances:
        all_configs = get_config_components()
        component_info = all_configs[component_name].copy()
        component_class = resolve_class(component_info.pop("class"))
        if "device_class" in component_info:
            # If a nested device is needed, resolve and initialize it first
            device_class = resolve_class(component_info.pop("device_class"))
            device_kwargs = component_info.pop("device_kwargs", {})
            device = device_class(**device_kwargs)
            _component_instances[component_name] = component_class(device, **component_info)
        else:
            _component_instances[component_name] = component_class(**component_info)
        logger.info(f"[{component_name}] class instantiated and added to component instances list")

    return _component_instances[component_name]

def with_lock(
        function_timeout: Optional[int] = None,
        acquisition_timeout: Optional[int] = None
) -> Callable[[Callable[Concatenate[str, P], None]], Callable[Concatenate[str, P], None]]:
    """
    Decorator that ensures exclusive execution of a function by using Redis-based locking.
    This decorator attempts to acquire a lock for a specified component and, if successful, maintains the lock for the
    duration of the function execution, up to a maximum of `function_timeout`. It waits to acquire the lock up to
    `acquisition_timeout` if it is currently held by another process.

    Args:
        function_timeout (Optional[int]): The maximum time in seconds to hold the lock after acquiring it for function
            execution. Defaults to config["function_timeout"].
        acquisition_timeout (Optional[int]): The maximum time in seconds to wait to acquire the lock if it is already
            held by another process. Defaults to config["acquisition_timeout"].

    Returns:
        Callable[[Callable[[str, ...], None]], Callable[[str, ...], None]]: A decorator function that, when applied to a
        target function, uses Redis to lock the function execution. This ensures exclusive access to the component
        specified by component_name` (a `str`) during execution. The decorated function still receives `component_name`
        as a `str`, with exclusive access guaranteed by the lock.
        
    Raises:
        LockError: If the lock cannot be acquired within the `acquisition_timeout` period.
        Exception: If an exception occurs during the function execution, a safety flag is set 
                    in Redis and an error is raised, which will trigger the emergency_stop function.

    Behavior:
        - When invoked, this decorator attempts to acquire a Redis lock specific to the `component_name`. If the lock
          is acquired, it automatically extends the lock's duration based on the specified `function_timeout`.
        - If the function completes normally or encounters an error, the lock is released immediately.
        - The decorator uses `acquisition_timeout` as the maximum wait time for acquiring the lock, helping to prevent
          indefinite waiting if the lock is already held.
        - The decorator uses 'function_timeout' to extend the lock timeout taking into account the estimated duration
          of the function

    Example:
        @with_lock(function_timeout=600, acquisition_timeout=300)
        def process_component(component_name, data):
            # Function code here, using `component_name` under exclusive lock
            pass

    Notes:
        - `function_timeout` should be chosen carefully to match the expected maximum duration of the function, as the
           lock will expire otherwise.
        - `acquisition_timeout` defines the maximum time to wait for lock acquisition, so consider the likelihood of
           concurrent processes accessing the same resource.
        - This decorator helps ensure exclusive access to resources in a distributed environment using Redis locks,
          ideal for managing concurrent processes.

    """
    config = {**DEFAULT_CONFIG}
    function_timeout = function_timeout if function_timeout is not None else config["function_timeout"]
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config["acquisition_timeout"]

    def decorator(func: Callable[Concatenate[str, P], None]) -> Callable[Concatenate[str, P], None]:
        @wraps(func)
        def wrapper(component_name: str, *args: P.args, **kwargs: P.kwargs) -> None:
            logger = get_run_logger()
            lock = acquire_lock(component_name, function_timeout, acquisition_timeout, func)
            try:
                return func(component_name, *args, **kwargs)  # Execute the original function
            except Exception as e:
                logger.error(f"An error occurred while executing {func.__name__}.: {e}")
                raise 
            finally:
                # Release the lock after the function completes
                if lock.owned():
                    lock.release()
                print(f"Lock released for {component_name}")

        return wrapper

    return decorator


def run_on_component() -> Callable[[Callable[Concatenate[str, P], None]], Callable[Concatenate[object, P], None]]:
    """
    Decorator to transform the first argument of a function (expected to be a component name) into the corresponding
    class instance. If the instance does not already exist, it is created based on the configuration in
    `CONFIG_COMPONENTS`. Once instantiated, the component instance is stored in `_component_instances` for reuse.

    Returns:
        Callable[[Callable[[str, ...], None]], Callable[[object, ...], None]]: A decorator function that, when applied
        to a target function, converts the first argument (`component_name`, a `str`) into the corresponding component
        instance. The decorated function receives this instance as its first argument, allowing direct interaction
        with the component.

    Raises:
        Exception: If an exception occurs during the function execution, a safety flag is set 
                    in Redis and an error is raised, which will trigger the emergency_stop function.

    Behavior:
        - If the specified `component_name` does not have an instance in `_component_instances`, this decorator will
          create a new instance using the configuration in `CONFIG_COMPONENTS`. Potentiostats are handled separately,
          while other components are instantiated using the class specified in the configuration.
        - After creating the instance, the decorator calls the decorated function with the component instance as the
          first argument.

    Example:
        @run_on_component()
        def calibrate(component, parameters):
            # Function code here, where 'component' is the instantiated object.
            pass

    Notes:
        - This decorator abstracts the component instantiation process, allowing functions to receive fully configured
          component instances instead of managing instantiation manually.
        - Instances are created once and reused to avoid object initialization procedure when not intended
        - If the function fails or raises an exception, a 'safety_operation' flag is set to 0 in Redis, triggering the
          emergency_stop function
    """

    def decorator(func: Callable[Concatenate[str, P], None]) -> Callable[Concatenate[object, P], None]:
        @wraps(func)
        def wrapper(component_name: str, *args: P.args, **kwargs: P.kwargs) -> None:
            component = get_or_create_component_instance(component_name)
            try:
                return func(component, *args, **kwargs)  # Execute the original function
            except Exception as e:
                raise RuntimeError(f"An error occurred while executing {func.__name__}.") from e

        return wrapper

    return decorator


def run_on_component_with_lock(
        function_timeout: Optional[int] = None,
        acquisition_timeout: Optional[int] = None
) -> Callable[[Callable[Concatenate[str, P], None]], Callable[Concatenate[object, P], None]]:
    """
    Decorator that combines Redis-based locking with automatic component instantiation. This decorator attempts to
    acquire a lock for the specified component. If acquired, it transforms the `component_name` argument into the
    corresponding class instance and then executes the decorated function with this instance, ensuring exclusive
    access to the component during execution.

    Args:
        function_timeout (Optional[int]): The maximum time in seconds to hold the lock after acquiring it for function
            execution. Defaults to config["function_timeout"].
        acquisition_timeout (Optional[int]): The maximum time in seconds to wait to acquire the lock if it is already
            held by another process. Defaults to config["acquisition_timeout"].

    Returns:
        Callable[[Callable[[str, ...], None]], Callable[[object, ...], None]]: A decorator function that initializes a
        component instance if needed and acquires a Redis lock for exclusive access to the component during function
        execution. The first argument (`component_name`, a `str`) is converted to the component instance (`object`),
        which is passed to the function.

    Raises:
        LockError: If the lock cannot be acquired within the `acquisition_timeout` period.
        Exception: If an exception occurs during the function execution, a safety flag is set 
                    in Redis and an error is raised, which will trigger the emergency_stop function.

    Behavior:
        - If the specified `component_name` does not have an instance in `_component_instances`, the decorator creates
          a new instance using `CONFIG_COMPONENTS`. Potentiostats are instantiated differently from other components.
        - Once instantiated, the component instance is stored in `_component_instances` and used as the first argument
          for the decorated function.
        - The decorator uses a Redis lock to ensure exclusive access to the component. If it successfully acquires
          the lock, it automatically extends the lock duration to match `function_timeout`.
        - After the function completes or if an error occurs, the lock is released and a Redis flag (`safety_operation`)
          is set to 0 in case of errors.

    Example:
        @run_on_component_with_lock(function_timeout=900, acquisition_timeout=300)
        def apply_cp(component, parameters):
            # Function code here, where 'component' is the instantiated object
            pass

    Notes:
        - This decorator provides both exclusive access (locking) and instance management, simplifying component-based
          operations with Redis locks.
        - `function_timeout` should be chosen carefully to match the expected maximum duration of the function, as the
          lock will expire otherwise.
        - `acquisition_timeout` defines the maximum time to wait for lock acquisition, so consider the likelihood of
          concurrent processes accessing the same resource.

    """

    config = {**DEFAULT_CONFIG}

    function_timeout = function_timeout if function_timeout is not None else config["function_timeout"]
    acquisition_timeout = acquisition_timeout if acquisition_timeout is not None else config["acquisition_timeout"]

    def decorator(func: Callable[Concatenate[str, P], None]) -> Callable[Concatenate[object, P], None]:
        @wraps(func)
        def wrapper(component_name: str, *args: P.args, **kwargs: P.kwargs) -> None:
            component = get_or_create_component_instance(component_name)
            lock = acquire_lock(component_name, function_timeout, acquisition_timeout, func)
            try:
                return func(component, *args, **kwargs)  # Execute the original function
            except Exception as e:
                raise RuntimeError(f"An error occurred while executing {func.__name__}.") from e
            finally:
                # Release the lock after the function completes
                if lock.owned():
                    lock.release()
                print(f"Lock released for {component_name}")

        return wrapper

    return decorator