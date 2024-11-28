import minimalmodbus
import redis
import os
import json
import pickle
from pathlib import Path
import traceback
import time
from math import ceil
from typing import Optional, Union, List, Any, Callable, Concatenate, ParamSpec
from functools import wraps
from prefect import task, flow

from default_config import DEFAULT_CONFIG, CONNECTIONS_INFO

from potentiostat_minimalmodbus_v00 import PotentiometerCommand
from matterlab_pumps import TecanXCPump
from peristaltic_pump import Longer_BT100_3J_Pump
from matterlab_valves import ValcoSelectionValve

_component_instances = {}
user_name = os.getenv("USER") or os.getenv("USERNAME")
_uv_vis_path =  Path(
    rf"C:\Users\{user_name}\Aspuru-Guzik Lab Dropbox\Lab Manager Aspuru-Guzik\PythonScript\HPLCMS_characterization\sample_to_measure"
)

CONFIG_COMPONENTS = {'longerWE01': {'class': Longer_BT100_3J_Pump, 'com_port': 'COM3', 'address': '1'},
                     'longerCE01': {'class': Longer_BT100_3J_Pump, 'com_port': 'COM3', 'address': '1'},
                     'tecanRX01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 2, 'syringe_volume': 2.5e-3,
                         'num_valve_port': 13,
                                   'ports': None},
                     'valveRX01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveRX01', 'num_port':10,
                                   'ports': None},
                     'tecanAZ01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 1, 'syringe_volume': 1e-3,
                                   'num_valve_port': 13,
                                   'ports': None},
                     'valveAZ01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveAZ01','num_port':10,
                                   'ports': None},
                     'potentiostat01': {'port': 'COM4', 'slaveaddress': 1}
                     }
for instrument in CONNECTIONS_INFO:
    CONFIG_COMPONENTS[instrument]['ports'] = {port: CONNECTIONS_INFO[instrument][port]['port'] for port in CONNECTIONS_INFO[instrument]}
CONFIG_SETUP_1 = ['potentiostat01', 'valve01', 'tecanAZ01', 'tecanRX01', 'longerCE01', 'longerWE01']


P = ParamSpec("P")

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
        Exception: If any exception occurs during the execution of the function: it is printed, and a safety operation
        flag is set to 0 in Redis, which will trigger the emergency_stop function.

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
        def wrapper(component_name: str, *args:P.args, **kwargs:P.kwargs) -> None:
            # Generate the object and a unique lock name for the pump
            ini_time = time.time()
            lock_name = f'{component_name}_lock'  # Unique identifier for the instance
            lock = client.lock(lock_name, timeout=acquisition_timeout)  # Create the lock with a timeout
            if lock.acquire(blocking=True):  # Attempt to acquire the lock
                try:
                    acquisition_time = time.time() - ini_time
                    lock.extend(timeout=function_timeout - acquisition_time)
                    return func(component_name, *args, **kwargs)  # Execute the original function
                except Exception as e:
                    print(f"Error in {func.__name__}: {e}")
                    client.set('safety_operation',0)
                finally:
                    # Release the lock after the function completes
                    if lock.owned():
                        lock.release()
                    print(f"Lock released for {component_name}")
            else:
                print(f"Could not acquire lock for {component_name}. Another process is blocking it.")
                client.set('safety_operation',0)

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
        Exception: If any exception occurs during the execution of the function: it is printed, and a safety operation
        flag is set to 0 in Redis, which will trigger the emergency_stop function.

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
        def wrapper(component_name: str, *args:P.args, **kwargs:P.kwargs) -> None:
            # Generate the object and a unique lock name for the pump
            if component_name not in _component_instances:
                # Generates an instance only if it does not exist
                component_info = CONFIG_COMPONENTS[component_name].copy()
                if 'potentiostat' in component_name:
                    potentiostat = minimalmodbus.Instrument(**component_info)
                    _component_instances[component_name] = PotentiometerCommand(potentiostat)
                else:
                    componentclass = component_info.pop('class')  # Extracts the class, rest are arguments
                    _component_instances[component_name] = componentclass(**component_info)

            # Use the already created instance
            component = _component_instances[component_name]
            try:
                return func(component, *args, **kwargs)  # Execute the original function
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                client.set('safety_operation', 0)


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
        Exception: If any exception occurs during the execution of the function: it is printed, and a safety operation
        flag is set to 0 in Redis, which will trigger the emergency_stop function.

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
        def wrapper(component_name: str, *args:P.args, **kwargs:P.kwargs) -> None:
            if component_name not in _component_instances:
                # Generates an instance only if it does not exist
                component_info = CONFIG_COMPONENTS[component_name].copy()
                if 'potentiostat' in component_name:
                    potentiostat = minimalmodbus.Instrument(**component_info)
                    _component_instances[component_name] = PotentiometerCommand(potentiostat)
                else:
                    componentclass = component_info.pop('class')  # Extrae la clase, los demás son argumentos
                    _component_instances[component_name] = componentclass(**component_info)

            # Use the already created instance
            component = _component_instances[component_name]
            # Generate the object and a unique lock name for the pump
            ini_time = time.time()
            lock_name = f'{component_name}_lock'  # Unique identifier for the instance
            lock = client.lock(lock_name, timeout=acquisition_timeout)  # Create the lock with a timeout
            if lock.acquire(blocking=True):  # Attempt to acquire the lock
                try:
                    acquisition_time = time.time() - ini_time
                    lock.extend(timeout= function_timeout -  acquisition_time)
                    return func(component, *args, **kwargs)  # Execute the original function
                except Exception as e:
                    print(f"Error in {func.__name__}: {e}")
                    client.set('safety_operation', 0)
                finally:
                    # Release the lock after the function completes
                    if lock.owned():
                        lock.release()
                    print(f"Lock released for {component_name}")
            else:
                print(f"Could not acquire lock for {component_name}. Another process is blocking it.")
                client.set('safety_operation', 0)

        return wrapper

    return decorator

@task
@run_on_component_with_lock(acquisition_timeout=20, function_timeout=15)
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
    try:
        pump.run(speed, direction)
        direction_sign = +1 if direction else -1
        client.set(str(pump),speed*direction_sign)
    except Exception as e:
        print(f'Error when running pump {pump}.\n'
              f'Exception: {e}')
        raise IOError

@task
def run_pump(
        pump: str,
        speed: float,
        direction: Optional[bool] = None,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries']

    run_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay
                               )(pump=pump, speed=speed, direction=direction)


@task
@run_on_component_with_lock(acquisition_timeout=20, function_timeout=15)
def stop_pump_func(pump: str) -> None:
    """
    Stops the specified pump.

    Args:
        pump (str): The name or identifier of the pump to stop.
    """
    try:
        pump.stop()
    except Exception as e:
        print(f'Error when stopping pump {pump}.\n'
              f'Exception: {e}')
        raise IOError


@task
def stop_pump(
        pump: str,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries']

    stop_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay)(pump)

@task
@run_on_component_with_lock(acquisition_timeout=20, function_timeout=15)
def check_pump_func(pump: str) -> float:
    """
    Checks the current status of the specified pump.

    Args:
        pump (str): The name or identifier of the pump to check.

    Returns:
        float: The current status of the pump: value indicates speed while the sign indicates direction (+ for
        counterclockwise and - for clockwise).
    """
    try:
        return pump.get_state()
    except Exception as e:
        print(f'Error in getting the state of pump {pump}.\n'
              f'Exception: {e}')
        raise IOError

@task
def check_pump(
        pump: str,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        **kwargs: Any,
)-> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['longer_retries']
    retries_delay = retries_delay if retries_delay is not None else config['longer_retries']

    return check_pump_func.with_options(retries=retries, retry_delay_seconds=retries_delay)(pump)
    
    
@task
@run_on_component_with_lock(acquisition_timeout=30, function_timeout=20*60)
def run_cp(
        potentiostat: str,
        current: float,
        time_rx: float
) -> None:
    """
    Runs chrono-potentiometry by applying a constant current for a specified duration.

    Args:
        potentiostat (str): The potentiostat used for the experiment.
        current (float): The current to apply (in A).
        time_rx (float): Duration to apply the current (in seconds).
    """
    potentiostat.apply_cp(current, time_rx)

@task
@run_on_component()
def switch_port_func(
        valve: str,
        port: str,
)-> None:
    """
    Switches the specified valve to a different port.

    Args:
        valve (str): The valve to operate.
        port (str): Identifier of the valve port to switch to.
    """
    try:
        valve.switch_port(port)
    except Exception as e:
        print(f'Error in {valve} when switching to port {port}.\n'
              f'Exception: {e}')
        raise IOError

@task
def switch_port_valve(
        valve: str,
        port: str,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        **kwargs: Any,
)-> None:
    config = {**DEFAULT_CONFIG,**kwargs}
    retries = retries if retries is not None else config['valve_retries']
    retries_delay = retries_delay if retries_delay is not None else config['valve_retries']
    
    switch_port_func.with_options(retries=retries, retry_delay_seconds=retries_delay
                                  )(valve, port)


@task
@run_on_component()
def draw_tecan_func(
        syringe_pump: str,
        volume: float,
        valve_port: Union[str, int],
        speed: float,
) -> None:
    """
    Draws a specified volume of liquid from a syringe pump.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to draw (in mL).
        valve_port (Union[str, int]): Identifier of the valve port to be used for drawing liquid.
        speed (float): The drawing speed to be set temporarily (in mL/s).
    """
    syringe_pump.draw(volume=volume, valve_port=valve_port, speed=speed)
    try:
        syringe_pump.draw(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as e:
        print(f'Error in drawing operation to port {valve_port} with {syringe_pump}.\n'
              f'Dispensing content to waste'
              f'Exception: {e}')
        syringe_pump.dispense_all(valve_port='air_waste', speed=speed)
        raise IOError

@task
@run_on_component()
def dispense_tecan_func(
        syringe_pump: str,
        volume: float,
        valve_port: Union[str, int],
        speed: float,
) -> None:
    """
    Dispenses a specified volume of liquid using a syringe pump.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to dispense (in mL).
        valve_port (Union[str, int]): Identifier of the valve port to be used for dispensing liquid.
        speed (float): The dispensing speed to be set temporarily (in mL/s).
    """
    try:
        syringe_pump.dispense(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as e:
        print(f'Error in dispensing operation to port {valve_port} with {syringe_pump}.\n'
              f'Dispensing content to waste'
              f'Exception: {e}')
        syringe_pump.dispense_all(valve_port='air_waste', speed=speed)
        raise IOError

@task
@run_on_component()
def draw_and_dispense_tecan_func(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0
) -> None:
    """
    Draws a specified volume of liquid from one valve and dispenses it to another.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to draw and dispense (in mL).
        draw_valve_port (Union[int, str]): Identifier of the valve port for drawing liquid.
        dispense_valve_port (Union[int, str]): Identifier of the valve port for dispensing liquid.
        speed (float): The speed to draw/dispense the liquid (in mL/s).
        wait (Optional[float]): Time to wait between drawing and dispensing (in seconds). Defaults to 0.
    
    Notes:
        - This function is only meant to be used in draw_and_dispense_tecan_unlock, draw_and_dispense_and_wash_tecan,
          and wash_syringe_unlock functions. Use carefully at other contexts.
        - It only draws and dispenses a specific amount from one port to the other. But should not be used for
          specific volume transfer between vessels.

    """
    draw_tecan_func(syringe_pump=syringe_pump, volume=volume, valve_port=draw_valve_port, speed=speed)
    time.sleep(wait)
    dispense_tecan_func(syringe_pump=syringe_pump, volume=volume, valve_port=dispense_valve_port, speed=speed)
    time.sleep(wait)

@flow
@run_on_component()
def draw_and_dispense_tecan(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        retries: Optional[int] = None,
        retries_delay: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Wrapper task for drawing and dispensing with retry logic and support for splitting large volumes into smaller iterations.

    Args:
        syringe_pump (str): The syringe pump to use for the operation.
        volume (float): The total volume of liquid to draw and dispense (in mL).
        draw_valve_port (Union[int, str]): Identifier of the valve port for drawing liquid.
        dispense_valve_port (Union[int, str]): Identifier of the valve port for dispensing liquid.
        speed (float): The speed to draw/dispense the liquid (in mL/s).
        wait (Optional[float]): Time to wait between drawing and dispensing in each iteration (in seconds). Defaults to 0.
        retries (Optional[int]): Maximum number of retries for each iteration. Defaults to DEFAULT_CONFIG['draw_and_dispense_retries'].
        retries_delay (Optional[float]): Delay between retries (in seconds). Defaults to DEFAULT_CONFIG['draw_and_dispense_retries_delay'].

    Behavior:
        - If the specified `volume` exceeds the syringe's maximum capacity, the function splits the operation
          into smaller iterations. Each iteration processes a portion of the total volume, calculated as
          `volume / dispense_iterations`.
        - Each iteration performs a call to `raw_and_dispense_tecan_func` with the calculated `volume_per_iteration`.
        - Retry logic is applied to each iteration individually, using the specified `retries` and `retries_delay`.
    """
    config = {**DEFAULT_CONFIG,**kwargs}
    retries = retries if retries is not None else config['draw_and_dispense_retries']
    retries_delay = retries_delay if retries_delay is not None else config['draw_and_dispense_retries_delay']

    dispense_iterations = ceil(volume / (1e3 * syringe_pump.syringe_volume))
    volume_per_iteration = volume / dispense_iterations

    for i in range(0, dispense_iterations):
        draw_and_dispense_tecan_func.with_options(
            retries=retries,
            retry_delay_seconds=retries_delay
        )(syringe_pump=syringe_pump, volume=volume_per_iteration, draw_valve_port=draw_valve_port,
          dispense_valve_port=dispense_valve_port, speed=speed, wait=wait)


@flow
def draw_and_dispense_tecan_unlocked(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        air_compensation_volume: Optional[float] = None,
        air_flush_factor: Optional[int] = None,
        air_flush_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Draws a specified amount of volume from a specified port, and dispenses it to a specified port.
    It does so, independently of whether the port is connected to the pump directly or through a selection valve.
    It does not generate a lock for the process.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to draw and dispense (in mL).
        draw_valve_port (Union[int, str]): Identifier of the valve port for drawing liquid.
        dispense_valve_port (Union[int, str]): Identifier of the valve port for dispensing liquid.
        speed (float): The speed to draw/dispense the liquid (in mL/s).
        air_compensation_volume (Optional[float]): Additional air volume to draw or dispense, to ensure
            accuracy in volume dispensed. Defaults to config["air_compensation_volume"]
        wait (Optional[float]): Time to wait between drawing and dispensing (in seconds). Defaults to 0.
        switch_valve_retries
        **kwargs (Any): Additional keyword arguments to override the default configuration.

    Behavior:
        - Depending on the syringe_pump name, selects the valve corresponding to that syringe pump.
        - If the draw_valve_port is not a stock solution (and therefore tube is empty/full of air), it draws all the
          air in the tube, from it end to the syringe_pump, taking into account syringe to valve tube volume if needed.
          This is to make sure all volume subtracted in following operation is liquid, with no air contribution.
        - An air_compensation_volume is added to account for the retarded movement of liquid when withdrawing air from
          the tub. Thus a higher volume is drawn than the actual volume of the tube. ***********************************************************************************
        - The volume specified is drawn and dispensed from draw_port_valve to dispense_port_valve, independently if
          those ports are connected directly to pump or through the corresponding valve.
        - Extra air volume is dispensed applying also an air_compensation_factor, to make sure all liquid falls into 
          the dispense_port_valve container.
    
    Notes:
        - This function does not take into account cases in which both draw_port_valve and dispense_port_valve are
          connected to the valve instead of directly to the pump.
          Be careful and make sure at least one of them is connected directly to the pump.
    """
    
    config = {**DEFAULT_CONFIG, **kwargs}
    air_compensation_volume = air_compensation_volume if air_compensation_volume is not None else config["air_compensation_volume"]
    air_flush_factor = air_flush_factor if air_flush_factor is not None else config["air_flush_factor"]
    air_flush_speed = air_flush_speed if air_flush_speed is not None else config["air_flush_speed"]

    # Select valve according to the pump type
    if 'RX' in syringe_pump.upper():
        syringe_valve = 'valveRX' + syringe_pump[-2:]
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]

    # Draw and dispense the required air from the input tube if needed
    input_air_volume = 0
    if draw_valve_port in CONNECTIONS_INFO[syringe_pump]:
        if CONNECTIONS_INFO[syringe_pump][draw_valve_port]['usage'].lower() != 'stock': #If is not a stock solution, tube is empty and air must be drawn before
            input_air_volume = CONNECTIONS_INFO[syringe_pump][draw_valve_port]['volume']
            input_air_volume = input_air_volume + air_compensation_volume
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_air_volume,
                                    draw_valve_port=draw_valve_port,dispense_valve_port='air_waste', **kwargs)
    else:
        input_air_volume = CONNECTIONS_INFO[syringe_pump]["valve"]['volume'] #Tube pump-valve will always be empty and air need to be drawn
        if CONNECTIONS_INFO[syringe_pump][draw_valve_port]['usage'].lower() != 'stock': #If it's not a stock solution, also need to drawn volume valve-compartment
            input_air_volume += CONNECTIONS_INFO[syringe_valve][draw_valve_port]['volume']
        input_air_volume = input_air_volume + air_compensation_volume

        switch_port_valve(valve=syringe_valve,port=draw_valve_port,**kwargs)
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_air_volume,
                                draw_valve_port='valve', dispense_valve_port='air_waste', **kwargs)
    
    #Draw/Dispense liquid + air if needed 
    air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume']*1000
    if (draw_valve_port in CONNECTIONS_INFO[syringe_pump]) and (dispense_valve_port in CONNECTIONS_INFO[syringe_pump]):
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=volume, draw_valve_port=draw_valve_port,
                                dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
        if input_air_volume > 0: #If the drawing port does not come from a stock solution, we want to leave it empty
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                    dispense_valve_port=dispense_valve_port, wait=wait, speed=air_flush_speed, **kwargs)
    else:
        if draw_valve_port in CONNECTIONS_INFO[syringe_pump]:
            draw_and_dispense_tecan(syringe_pump=syringe_pump,volume=volume, draw_valve_port=draw_valve_port,
                                    dispense_valve_port='valve', wait=wait, speed=speed, **kwargs)
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                    dispense_valve_port='valve', wait=wait, speed=speed, **kwargs)
            if input_air_volume > 0:  # If the drawing port does not come from a stock solution, we want to leave it empty
                draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_air_volume, draw_valve_port='air',
                                        dispense_valve_port='valve', wait=wait, speed=air_flush_speed, **kwargs)
        else:
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=volume, draw_valve_port='valve',
                                    dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                    dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
            if input_air_volume > 0:  # If the drawing port does not come from a stock solution, we want to leave it empty
                draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                        dispense_valve_port=dispense_valve_port, wait=wait, speed=air_flush_speed, **kwargs)

@flow
def wash_syringe_unlocked(
        syringe_pump: str,
        repeats: int,
        wash_vol: float,
        speed: float,
        wash_valve: bool,
        air_flush_factor: Optional[int] = None,
        air_flush_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Washes the syringe a specified number of times with the given volume and speed. If specified, also washes the
    valve associated with the pump.
    It does not generate a lock for the process

    Args:
        syringe_pump (str): The syringe pump to use for washing.
        repeats (int): Number of washing cycles.
        wash_vol (float): Volume (in mL) to wash with.
        pump_speed (float): Speed of the syringe during washing (in mL/s).
        wash_valve (bool): Whether to wash the valve.
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    air_flush_factor = air_flush_factor if air_flush_factor is not None else config['air_flush_factor']
    air_flush_speed = air_flush_speed if air_flush_speed is not None else config["air_flush_speed"]

    #Syringe washing
    for _ in range(repeats):
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                dispense_valve_port='air_waste', speed=speed, **kwargs)

    #Valve washing
    if wash_valve:
        # Select valve according to the pump type
        if 'RX' in syringe_pump.upper():
            syringe_valve = 'valveRX' + syringe_pump[-2:]
        else:
            syringe_valve = 'valveAZ' + syringe_pump[-2:]

        switch_port_valve(valve=syringe_valve, port='air_waste', **kwargs)

        air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                dispense_valve_port='valve', speed=speed, **kwargs)
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                dispense_valve_port='valve', speed=air_flush_speed, **kwargs)


@flow
@with_lock()
def draw_and_dispense_and_wash_tecan(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        wash_repeats: Optional[float] = None,
        wash_vol: Optional[float] = None,
        wash_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Performs a draw and dispense operation followed by a syringe wash operation, using the same lock.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to draw and dispense (in mL).
        draw_valve_port (Union[int, str]): The valve port for drawing liquid.
        dispense_valve_port (Union[int, str]): The valve port for dispensing liquid.
        speed (float): The speed to draw/dispense the liquid (in mL/s).
        wait (Optional[float]): Time to wait between drawing and dispensing (in seconds). Defaults to 0.
        wash_repeats (Optional[int]): Number of washing cycles. Defaults to config['syringe_wash_repeats'].
        wash_vol (Optional[float]): Volume (in mL) to wash with. Defaults to config['syringe_wash_volume_RX'] or
                                    config['syringe_wash_volume_AZ'] depending on specified syringe pump.
        wash_speed (Optional[float]): Speed of the syringe during washing (in mL/s). Defaults to config['syringe_wash_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """

    config = {**DEFAULT_CONFIG, **kwargs}

    # Use provided arguments or fall back to default config
    wash_repeats = wash_repeats if wash_repeats is not None else config['syringe_wash_repeats']
    wash_speed = wash_speed if wash_speed is not None else config['syringe_wash_speed']
    if wash_vol is not None:
        wash_vol = wash_vol
    else:
        wash_vol = config['syringe_wash_volume_RX'] if 'RX' in syringe_pump else config['syringe_wash_volume_AZ']

    draw_and_dispense_tecan_unlocked(
        syringe_pump, volume=volume, draw_valve_port=draw_valve_port,
        dispense_valve_port=dispense_valve_port, speed=speed, wait=wait, **kwargs,
    )
    if (draw_valve_port not in DEFAULT_CONFIG[syringe_pump]['ports']) or (dispense_valve_port not in DEFAULT_CONFIG[syringe_pump]['ports']):
        wash_syringe_unlocked(syringe_pump=syringe_pump, repeats=wash_repeats, wash_vol=wash_vol, pump_speed=wash_speed,
                              wash_valve=True, **kwargs)
    else:
        wash_syringe_unlocked(syringe_pump=syringe_pump, repeats=wash_repeats, wash_vol=wash_vol, pump_speed=wash_speed,
                              wash_valve=False, **kwargs)

@flow
@with_lock()
def wash_compartment(
        syringe_pump: str,
        compartment: str,
        repeats: Optional[int] = None,
        wash_vol: Optional[float] = None,
        speed: Optional[float] = None,
        speed_last_empty: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Washes the specified compartment. Designed for washing 'WE/CE_vial' or 'vials'

    Args:
        syringe_pump (str): Syringe pump to use.
        compartment (str): Compartment to be washed, e.g., 'WE_vial' or 'CE_vial'.
        repeats (Optional[int]): Number of wash cycles. Defaults to config['wash_compartment_repeats'].
        wash_vol (Optional[float]): Volume of water for each wash step (in mL). Defaults to config['wash_compartment_volume'].
        speed (Optional[float]): Draw/dispense speed (in mL/s). Defaults to config['wash_compartment_speed'].
        speed_last_empty (Optional[float]): Speed for the final emptying step (in mL/s). Defaults to config['wash_compartment_speed_last_empty'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    repeats = repeats if repeats is not None else config['wash_compartment_repeats']
    wash_vol = wash_vol if wash_vol is not None else config['wash_compartment_volume']
    speed = speed if speed is not None else config['wash_compartment_speed']
    speed_last_empty = speed_last_empty if speed_last_empty is not None else config['wash_compartment_speed_last_empty']

    if 'RX' in syringe_pump: #Take volume in the compartment
        volume = float(client.get(f"{compartment}_volume"))
    else: #If it's a vial, just take the full volume inside vial
        volume = config['vial_full_volume']

    draw_and_dispense_tecan_unlocked(syringe_pump=syringe_pump, volume=volume, draw_valve_port=compartment, 
                                     dispense_valve_port='air_waste', speed=speed, **kwargs)
    client.set(compartment + '_volume',0)

    for _ in range(repeats):
        draw_and_dispense_tecan_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                         dispense_valve_port=compartment, speed=speed, **kwargs)
        draw_and_dispense_tecan_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port=compartment,
                                         dispense_valve_port='air_waste', speed=speed, **kwargs)
        
    draw_and_dispense_tecan_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port=compartment,
                                     dispense_valve_port='air_waste',
                                     speed=speed_last_empty, **kwargs)

@flow
def fill_compartment(
        source: str,
        destination: str,
        volume: float,
        pump_speed: float,
        **kwargs: Any,
) -> None:
    """
    Transfers liquid from one compartment to another using a syringe pump and updates destination compartment volume accordingly

    Args:
        source (str): The name of the source compartment from which the liquid will be transferred.
        destination (str): The name of the destination compartment to which the liquid will be transferred.
        volume (float): The amount of liquid to transfer (in mL).
        pump_speed (float): The speed at which the liquid is transferred (in mL/s).
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    draw_and_dispense_and_wash_tecan(
        syringe_pump='tecanRX01', volume=volume, draw_valve_port=source,
        dispense_valve_port=destination, speed=pump_speed,**kwargs
    )
    client.set(f"{destination}_volume", client.get(f"{source}_volume"))
    #client.set(f"{source}_volume", float(client.get(f"{source}_volume"))-volume)


@flow
@with_lock()
def initialize_pump(
        syringe_pump: str,
        speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    This function fills the compartment-syringe/valve tube with liquid for all stock solution ports, leaving them ready
    for their direct liquid subtraction.

    Args:
        syringe_pump (str): The syringe pump to use.
        speed (Optional[float]): The speed to draw/dispense the air (in mL/s).
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    speed = speed if speed is not None else config["syringe_initialization_speed"]

    # Select valve according to the pump type
    if 'RX' in syringe_pump.upper():
        syringe_valve = 'valveRX' + syringe_pump[-2:]
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]

    # Filling of all the stock solution tubes leading to the pump valve directly
    for port_name, port_info in CONNECTIONS_INFO[syringe_pump].items():
        if port_info['usage'].lower() == 'stock':
            input_tube_volume = port_info['volume']
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port=port_name, 
                                    dispense_valve_port="air_waste", speed=speed, **kwargs)

    # Filling of al stock solution tubes leading to the valve assigned to the pump
    wash_valve = False
    for port_name, port_info in CONNECTIONS_INFO[syringe_valve].items():
        if port_info['usage'].lower() == 'stock':
            input_tube_volume = port_info['volume']
            switch_port_valve(valve=syringe_valve, port=port_name, **kwargs)
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port="valve", 
                                    dispense_valve_port="air_waste", speed=speed, **kwargs)
            wash_valve = True

    wash_syringe_unlocked(syringe_pump, wash_valve=wash_valve, **kwargs)


@flow
def empty_and_stop_pumps(
        wash_time: float,
        speed: float,
        **kwargs: Any,
) -> None:
    """
    Empties the flow cell after a process by running pumps in reverse to clear residues.

    Args:
        wash_time (float): Duration of the pump run in the reverse direction (seconds).
        pump_speed (float): Speed of the peristaltic pumps (rpm).
    """
    
    run_pump(pump='longerWE01', speed=speed, direction=False, **kwargs)
    run_pump(pump='longerCE01', speed=speed, direction=False, *kwargs)
    time.sleep(wash_time)
    client.set('flow_cell_content','empty_contaminated')
    stop_pump(pump='longerWE01', *kwargs)
    stop_pump(pump='longerCE01', *kwargs)


@flow
def wash_flow_cell(
        repeats: Optional[int] = None,
        wash_time: Optional[float] = None,
        speed: Optional[float] = None,
        wash_volume: Optional[float] = None,
        filling_speed: Optional[float] = None,
        wash_comp_repeats: Optional[int] = None,
        wash_comp_volume: Optional[float] = None,
        wash_comp_speed: Optional[float] = None,
        wash_comp_speed_last_empty: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Washes the interior of the flow cell by repeating cycles of emptying, flushing with water, and re-emptying.

    Args:
        repeats (Optional[int]): Number of wash cycles to repeat. Defaults to config['wash_flow_cell_repeats'].
        wash_time (Optional[float]): Duration for flushing the cell (seconds). Defaults to config['wash_flow_cell_time'].
        speed (Optional[float]): Pump speed during flushing (rpm). Defaults to config['wash_flow_cell_speed'].
        wash_volume (Optional[float]): Volume dispensed during each wash cycle (mL). Defaults to config['wash_flow_cell_wash_comp_volume'].
        filling_speed (Optional[float]): Pump speed for filling compartments (mL/s). Defaults to config['wash_flow_cell_filling_speed'].
        wash_comp_repeats (Optional[int]): Number of wash cycles per compartment. Defaults to config['wash_flow_cell_wash_comp_repeats'].
        wash_comp_volume (Optional[float]): Volume for each wash of compartments (mL). Defaults to config['wash_flow_cell_wash_comp_volume'].
        wash_comp_speed (Optional[float]): Pump speed for compartment washing (mL/s). Defaults to config['wash_flow_cell_wash_comp_speed'].
        wash_comp_speed_last_empty (Optional[float]): Speed for final emptying of compartments (mL/s). Defaults to config['wash_flow_cell_wash_comp_speed_last_empty'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG,**kwargs}

    repeats = repeats if repeats is not None else config['wash_flow_cell_repeats']
    wash_time = wash_time if wash_time is not None else config['wash_flow_cell_time']
    speed = speed if speed is not None else config['wash_flow_cell_speed']
    filling_speed = filling_speed if filling_speed is not None else config['wash_flow_cell_filling_speed']
    wash_comp_repeats = wash_comp_repeats if wash_comp_repeats is not None else config['wash_flow_cell_wash_comp_repeats']
    wash_comp_volume = wash_comp_volume if wash_comp_volume is not None else config['wash_flow_cell_wash_comp_volume']
    wash_comp_speed = wash_comp_speed if wash_comp_speed is not None else config['wash_flow_cell_wash_comp_speed']
    wash_comp_speed_last_empty = wash_comp_speed_last_empty if wash_comp_speed_last_empty is not None else config['wash_flow_cell_wash_comp_speed_last_empty']

    empty_and_stop_pumps(wash_time, speed,**kwargs)

    for _ in range(repeats):
        fill_compartment('water', 'WE_vial01', wash_volume, filling_speed)
        fill_compartment('water', 'CE_vial01', wash_volume, filling_speed)
        run_pump('longerWE01', speed)
        run_pump('longerCE01', speed)
        client.set('flow_cell_content','water_contaminated')
        time.sleep(wash_time)

        wash_compartment('tecanRX01', 'WE_vial01', repeats=wash_comp_repeats, wash_vol=wash_comp_volume,
                         pump_speed=wash_comp_speed, pump_speed_last_empty=wash_comp_speed_last_empty)
        wash_compartment('tecanRX01', 'CE_vial01', repeats=wash_comp_repeats, wash_vol=wash_comp_volume,
                         pump_speed=wash_comp_speed, pump_speed_last_empty=wash_comp_speed_last_empty)

        empty_and_stop_pumps(wash_time, speed,**kwargs)

    client.set('flow_cell_content','clean')
    client.set('WE_vial01_volume', 0)
    client.set('CE_vial01_volume', 0)

@flow
@with_lock(function_timeout=900)
def mix_metals(
        syringe_pump: str,
        metal_ratios: List[float] = None,
        deposition_volume: Optional[float] = None,
        filling_speed: Optional[float] = None,
        mixing_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Prepares a metal solution in the 'WE_vial' based on specified ratios and volume.

    Args:
        syringe_pump (str): Identifier for the syringe pump to use.
        metal_ratios (List[float]): List of metal ratios (e.g., [Cu, Co, Ni]).
        deposition_volume (Optional[float]): Total volume of solution to prepare (mL). Defaults to config['electrodeposition_deposition_volume'].
        filling_speed (Optional[float]): Draw/dispense speed (mL/s). Defaults to config['electrodeposition_filling_speed'].
        mixing_speed (Optional[float]): Dispense speed during mixing (mL/s). Defaults to config['electrodeposition_mixing_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    # Use provided arguments or fall back to default config
    deposition_volume = deposition_volume if deposition_volume is not None else config['electrodeposition_deposition_volume']
    filling_speed = filling_speed if filling_speed is not None else config['electrodeposition_filling_speed']
    mixing_speed = mixing_speed if mixing_speed is not None else config['electrodeposition_mixing_speed']

    compositions = [ratio / sum(metal_ratios) for ratio in metal_ratios]
    volumes = [comp * deposition_volume for comp in compositions]

    for vol, metal in zip(volumes, ['Cu', 'Co', 'Ni']):
        draw_and_dispense_and_wash_tecan(syringe_pump=syringe_pump, volume=vol, draw_valve_port=metal, 
                                         dispense_valve_port='WE_vial01', speed=filling_speed)

    draw_and_dispense_and_wash_tecan(syringe_pump=syringe_pump, volume=deposition_volume * 0.5,
                                    draw_valve_port='WE_vial01', dispense_valve_port='WE_vial01', speed=mixing_speed)  # Mix the solution slightly
    
    client.set('WE_vial01_volume', deposition_volume)

@flow
def electrodeposition(
        metal_ratios: List[float],
        current: Optional[float] = None,
        time_rx: Optional[float] = None,
        deposition_volume: Optional[float] = None,
        anolyte_volume: Optional[float] = None,
        pump_speed: Optional[float] = None,
        filling_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Conducts metal electrodeposition using specified metal ratios, current, and time.

    Args:
        metal_ratios (List[float]): Metal ratios for electrodeposition (e.g., [Cu, Co, Ni]).
        current (Optional[float]): Current applied (A). Defaults to config['electrodeposition_current'].
        time_rx (Optional[float]): Duration for current application (s). Defaults to config['electrodeposition_time'].
        deposition_volume (Optional[float]): Solution volume (mL) prepared and used. Defaults to config['electrodeposition_deposition_volume'].
        anolyte_volume (Optional[float]): Volume of anolyte solution (mL). Defaults to config['electrodeposition_anolyte_volume'].
        pump_speed (Optional[float]): Pump speed during electrodeposition (rpm). Defaults to config['electrodeposition_pump_speed'].
        filling_speed (Optional[float]): Speed for filling compartments (mL/s). Defaults to config['electrodeposition_filling_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    current = current if current is not None else config['electrodeposition_current']
    time_rx = time_rx if time_rx is not None else config['electrodeposition_time']
    deposition_volume = deposition_volume if deposition_volume is not None else config['electrodeposition_deposition_volume']
    anolyte_volume = anolyte_volume if anolyte_volume is not None else config['electrodeposition_anolyte_volume']
    pump_speed = pump_speed if pump_speed is not None else config['electrodeposition_pump_speed']
    filling_speed = filling_speed if filling_speed is not None else config['electrodeposition_filling_speed']

    mix_metals(syringe_pump='tecanRX01', metal_ratios=metal_ratios, deposition_volume=deposition_volume,**kwargs)
    fill_compartment('anolyte', 'CE_vial01', anolyte_volume, filling_speed, **kwargs)

    run_pump('longerWE01', pump_speed)
    run_pump('longerCE01', pump_speed)
    run_cp('potentiostat01', current, time_rx)
    client.set('flow_cell_content','metal_salts')

    wash_flow_cell(**kwargs)

@flow
def reaction(
        catholyte: str,
        current: Optional[float] = None,
        time_rx: Optional[float] = None,
        catholyte_volume: Optional[float] = None,
        anolyte_volume: Optional[float] = None,
        pump_speed: Optional[float] = None,
        filling_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Runs a reaction using the specified catholyte, applying a current for a set duration.

    Args:
        catholyte (str): Type of catholyte used for the reaction.
        current (Optional[float]): Applied current (A). Defaults to config['reaction_current'].
        time_rx (Optional[float]): Duration of the reaction (s). Defaults to config['reaction_time'].
        catholyte_volume (Optional[float]): Volume of catholyte (mL). Defaults to config['reaction_catholyte_volume'].
        anolyte_volume (Optional[float]): Volume of anolyte (mL). Defaults to config['reaction_anolyte_volume'].
        pump_speed (Optional[float]): Pump speed during reaction (rpm). Defaults to config['reaction_pump_speed'].
        filling_speed (Optional[float]): Speed for filling compartments (mL/s). Defaults to config['reaction_filling_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    current = current if current is not None else config['reaction_current']
    time_rx = time_rx if time_rx is not None else config['reaction_time']
    catholyte_volume = catholyte_volume if catholyte_volume is not None else config['reaction_catholyte_volume']
    anolyte_volume = anolyte_volume if anolyte_volume is not None else config['reaction_anolyte_volume']
    pump_speed = pump_speed if pump_speed is not None else config['reaction_pump_speed']
    filling_speed = filling_speed if filling_speed is not None else config['reaction_filling_speed']

    client.set('reaction_status', "0")
    fill_compartment(catholyte, 'WE_vial01', catholyte_volume, filling_speed, **kwargs)
    fill_compartment('anolyte', 'WE_vial01', anolyte_volume, filling_speed, **kwargs)

    run_pump('longerWE01', pump_speed, *kwargs)
    run_pump('longerCE01', pump_speed, *kwargs)

    client.set('reaction_status', time_rx)
    client.set('flow_cell_content',catholyte)
    run_cp('potentiostat01', current, time_rx)
    client.set('reaction_status', "waiting")

    wash_flow_cell(**kwargs)

@flow
def take_aliquots(
        num_aliquots: Optional[int] = None,
        volume: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Takes aliquots during a reaction, mixes with detection reagents, and records each step.

    Args:
        num_aliquots (Optional[int]): Number of aliquots to take. Defaults to config['aliquote_number'].
        volume (Optional[float]): Volume for each aliquot (mL). Defaults to config['aliquote_volume'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    
    Notes:
        - Take into account the maximum number of vials and cells running on parallel. 
          nun_aliquots * num_cells <= num_vials
        - Structure of dumped in filled_vials variable in Redis 
         [ vial: vial valve port name where the aliquot has been sent,
         time_lim: time when sample need to be sent to UV-VIS (30min in dark after acquisition),
         time_rxn: Time when aliquot was acquired approximately ]
    """
    
    config = {**DEFAULT_CONFIG, **kwargs}

    # Use provided arguments or fall back to default config
    num_aliquots = num_aliquots if num_aliquots is not None else config['aliquote_number']
    volume = volume if volume is not None else config['aliquote_volume']

    while True:
        reaction_status = client.get('reaction_status')
        if reaction_status == "waiting":
            time.sleep(20)
        elif reaction_status == "0":
            time.sleep(0.1)
        else:
            initial_time = time.time()
            aliquotes_sent = 0
            aliquote_interval = (float(reaction_status) - 60) / num_aliquots
            period_timing = time.time() + aliquote_interval - 30

            while aliquotes_sent < num_aliquots:
                current_time = time.time()

                if period_timing <= current_time:
                    for cell in ['WE_vial01',]:
                        empty_vials = [json.loads(item) for item in client.lrange('empty_vials', 0, -1)]

                        if empty_vials:
                            vial = empty_vials.pop(0)
                            client.delete('empty_vials')

                            for item in empty_vials:
                                client.rpush('empty_vials', json.dumps(item))

                            draw_and_dispense_and_wash_tecan(
                                'tecanAz01', volume=volume, draw_valve_port=cell,
                                dispense_valve_port=vial, speed=config['aliquot_filling_speed'], **kwargs
                            )
                            aliquot_time = time.time()
                            fill_vial_detection_mix(vial, aliquot_filling_speed = config['aliquot_filling_speed']
                                                    ,**kwargs)
                            aliquot_time = (aliquot_time + time.time())/2
                            vial_info = [vial, current_time + 30 * 60, aliquot_time - initial_time]
                            client.rpush('filled_vials', json.dumps(vial_info))

                            aliquotes_sent += 1
                            period_timing += aliquote_interval
                        else:
                            print('Warning! There are no empty vials, waiting for one to get free')
                            time.sleep(5)
                time.sleep(2.5)

@task
def generate_pickle_file(
        compositions_str: str,
        elyte:str,
        time_rxn: int,
) -> None:
    """
    Generates a pickle file with the following structure: 
    "comp_{ratio_Cu}_{ratio_Co}_{ratio_Ni}_{electrolyte}_{reaction_time}s.pkl
    In the metal ratios the decimal dot has been suppressed. Ej: 0.500 -> 0500
    
    Args:
        compositions_str (str): String representing composition ratios of Cu, Co, Ni.
        elyte (str): electrolyte used.
        time_rxn (int): Time at which the sample was acquired.
    """
    data = {
        "injection_name": f"compn_{compositions_str}_{elyte}_{time_rxn}s.txt",
        "target_name": "",
        "retention_time": 1,
        "vial_number": None,
        "average_absorbance_peak": 250,
        "average_absorbance_375": 250,
        "sample_volume": 0.1
    }
    full_path = _uv_vis_path / f"{data['injection_name']}.pkl"
    with open(full_path, "wb") as f:
        pickle.dump(data, f)

@flow
def measure_vials(
        wash_vial_repeats: Optional[int] = None,
        wash_vial_volume: Optional[float] = None,
        wash_vial_speed: Optional[float] = None,
        wash_vial_last_empty: Optional[float] = None,
        filling_speed: Optional[float] = None,
        **kwargs: Any
) -> None:
    """
    Monitors the list of filled vials and initiates measurement by sending each to the UV-VIS spectrometer
    when the specified time arrives. Performs vial washing after measurement.

    Args:
        wash_vial_repeats (Optional[int]): Number of washing repetitions for each vial after measurement.
        wash_vial_volume (Optional[float]): Volume used per wash step (in mL).
        wash_vial_speed (Optional[float]): Pump speed during washing (in mL/s).
        wash_vial_last_empty (Optional[float]): Speed for the final emptying step (in mL/s).
        filling_speed (Optional[float]): Speed for filling aliquots (in mL/s).
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    # Using conditional assignments with provided parameters or defaults
    wash_vial_repeats = wash_vial_repeats if wash_vial_repeats is not None else config['wash_vial_repeats']
    wash_vial_volume = wash_vial_volume if wash_vial_volume is not None else config['wash_vial_volume']
    wash_vial_speed = wash_vial_speed if wash_vial_speed is not None else config['wash_vial_speed']
    wash_vial_last_empty = wash_vial_last_empty if wash_vial_last_empty is not None else config['wash_vial_last_empty']
    filling_speed = filling_speed if filling_speed is not None else config['aliquot_filling_speed']

    while True:
        # Retrieve list of filled vials
        filled_vials = [json.loads(item) for item in client.lrange('filled_vials', 0, -1)]
        updated_list = []

        if filled_vials:
            for item in filled_vials:
                vial, time_lim, time_rxn = item
                time_lim = float(time_lim)
                if time.time() > time_lim:
                    draw_and_dispense_and_wash_tecan(
                        'tecanAZ01', 0.5, draw_valve_port=vial, dispense_valve_port='uv-vis',
                        speed=filling_speed, **kwargs
                    )
                    generate_pickle_file(elyte=client.get('reaction_catholyte'),
                                         compositions_str=client.get('reaction_metal_ratios'),
                                         time_rxn = round(float(time_rxn)))
                    wash_compartment('tecanAZ01', vial,wash_vial_repeats,wash_vial_volume,
                                     wash_vial_speed,wash_vial_last_empty)
                    client.rpush('empty_vials', json.dumps(vial))

                    time.sleep(360)  # Wait 6 minutes to ensure UV-VIS measurement completes
                else:
                    updated_list.append(item)

            # Update the filled vials list
            client.delete('filled_vials')
            for item in updated_list:
                client.rpush('filled_vials', json.dumps(item))

        time.sleep(15)

@flow
@with_lock()
def fill_vial_detection_mix(
        vial: str,
        aliquot_volume: Optional[float] = None,
        d1_volume: Optional[float] = None,
        d2_volume: Optional[float] = None,
        d3_volume: Optional[float] = None,
        aliquot_filling_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Prepares a detection reagent mix in the specified vial for the indophenol blue method.

    Args:
        vial (str): Vial identifier for the mix preparation.
        aliquot_volume (Optional[float]): Volume of aliquot to be added.
        d1_volume (Optional[float]): Volume of detection reagent 1.
        d2_volume (Optional[float]): Volume of detection reagent 2.
        d3_volume (Optional[float]): Volume of detection reagent 3.
        aliquot_filling_speed (Optional[float]): Pump speed for filling (in mL/s).
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    # Use provided arguments or fall back to default config
    aliquot_volume = aliquot_volume if aliquot_volume is not None else config['aliquot_volume']
    d1_volume = d1_volume if d1_volume is not None else config['detection_reagent_1_volume']
    d2_volume = d2_volume if d2_volume is not None else config['detection_reagent_2_volume']
    d3_volume = d3_volume if d3_volume is not None else config['detection_reagent_3_volume']
    aliquot_filling_speed = aliquot_filling_speed if aliquot_filling_speed is not None else config['aliquot_filling_speed']

    draw_and_dispense_tecan_unlocked(
        'tecanAZ01', volume=0.2 - aliquot_volume, draw_valve_port='water',
        dispense_valve_port=vial, speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d1_volume, 'd1', vial,
                                     speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d2_volume, 'd2', vial,
                                     speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d3_volume, 'd3', vial,
                                     speed=aliquot_filling_speed, **kwargs)

@flow
def electrodisolution(
        time_rx: Optional[float] = None,
        catholyte_volume: Optional[float] = None,
        anolyte_volume: Optional[float] = None,
        pump_speed: Optional[float] = None,
        filling_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Conducts an electrochemical dissolution of the catalyst layer under open circuit potential
    in acidic conditions for a specified time.

    Args:
        time_rx (Optional[float]): Duration for the dissolution (in seconds).
        catholyte_volume (Optional[float]): Catholyte volume used in the reaction (in mL).
        anolyte_volume (Optional[float]): Anolyte volume used in the reaction (in mL).
        pump_speed (Optional[float]): Pump speed during reaction (in rpm).
        filling_speed (Optional[float]): Pump speed for filling compartment (in mL/s).
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    # Using conditional assignments with provided parameters or defaults
    time_rx = time_rx if time_rx is not None else config['electrodisolution_time']
    catholyte_volume = catholyte_volume if catholyte_volume is not None else config['electrodisolution_catholyte_volume']
    anolyte_volume = anolyte_volume if anolyte_volume is not None else config['electrodisolution_anolyte_volume']
    pump_speed = pump_speed if pump_speed is not None else config['electrodisolution_pump_speed']
    filling_speed = filling_speed if filling_speed is not None else config['electrodisolution_filling_speed']

    fill_compartment('acid', 'WE_vial01', catholyte_volume, filling_speed, **kwargs)
    fill_compartment('anolyte', 'CE_vial01', anolyte_volume, filling_speed, **kwargs)

    run_pump('longerCE01', pump_speed)
    run_pump('longerWE01', pump_speed)

    client.set('flow_cell_content','acid')
    run_cp('potentiostat01', 0, time_rx)

    wash_flow_cell(**kwargs)

@flow
def main_reaction_loop(
        metal_ratios: List[float],
        **kwargs: Any,
)->None:
    """
    Executes the main reaction loop, which includes electrodeposition, reaction, and dissolution
    based on given metal ratios for catalyst composition.

    Args:
        metal_ratios (List[float]): List of metal ratios [Cu, Co, Ni].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    compositions = [round(ratio / sum(metal_ratios), 3) for ratio in metal_ratios]
    compositions_str = "_".join(f"{c:.2f}".replace(".", "") for c in compositions)
    for catholyte_num in range(0,9):
        catholyte = 'elyte' + str(catholyte_num)
        client.set('reaction_catholyte', catholyte)
        client.set('reaction_metal_ratios',compositions_str)
        electrodeposition(metal_ratios,current=config['electrodeposition_current'],
                          time=config['electrodeposition_time'],
                          deposition_volume=config['electrodeposition_catholyte_volume'],
                          anolyte_volume=config['electrodeposition_anolyte_volume'],
                          pump_speed=config['electrodeposition_pump_speed'])
        reaction(catholyte, **kwargs)
        electrodisolution(**kwargs)

@flow
def pumps_safety_check(**kwargs)->None:
    """
    Continuously monitors the status of pumps, verifying they operate as expected.
    Attempts to restart pumps if discrepancies are detected, and triggers an emergency stop if errors persist.
    """
    while True:
        pumps_list = [pump for pump in CONFIG_COMPONENTS if 'longer' in pump.lower()]
        for pump in pumps_list:
            expected_status = float(client.get(pump))
            actual_status = check_pump(pump)
            if actual_status != expected_status:
                time.sleep(5)
                expected_status = float(client.get(pump))
                direction = True if float(expected_status) > 0 else False
                speed = abs(float(expected_status))
                run_pump(pump,speed,direction,**kwargs)
                actual_status = check_pump(pump)
                if actual_status != expected_status:
                    client.set('safe_operation',0)
        time.sleep(15)

@flow
def emergency_stop(**kwargs: Any)->None:
    """
    Activates emergency procedures when safe operation is compromised, ensuring the flow cells are emptied
    and cleaned to avoid contamination.

    Args:
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    while True:
        if client.get('safety_operation')=='0':
            for _ in range(3):
                try:
                    empty_and_stop_pumps(config['wash_flow_cell_time'],config['wash_flow_cell_speed'],
                                         retries=config['longer_retries_emergency_stop'],
                                         retries_delay=config['longer_retries_delay_emergency_stop'])
                    print('An error happened, flow cell emptied and cleaned without problems')
                    break
                except Exception as e:
                    print(f'An error occurred: {e}')
                    traceback.print_exc()
                if _ == 2:
                    status = client.get('flow_cell_content')
                    print(f'Warning, an error happened, flow cell could not be cleaned properly. \n '
                          f'flow cell content is {status}')

        time.sleep(30)

if __name__ == ("__main__"):
    client = redis.StrictRedis(
        host="adrastea",
        port=6379,
        password="potato12",
        decode_responses=True
    )
    # Variables to track volume on each compartment
    client.set('WE_vial01_volume', 0)
    client.set('CE_vial01_volume', 0)
    client.set('WE_vial02_volume', 0)
    client.set('CE_vial02_volume', 0)
    # Variables to track filled and empty vials
    client.rpush('empty_vials', *['vial1', 'vial2', 'vial3', 'vial4', 'vial5', 'vial6', 'vial7', 'vial8'])
    client.delete('filled_vials')
    # Variables to track reaction status and safety
    client.set('reaction_catholyte', '')
    client.set('reaction_metal_ratios', '')
    client.set('reaction_status', 'waiting')
    client.set('flow_cell_content', 'clean')
    client.set('safety_operation', 1)
    # Variables to track pump status
    client.set('longerWE01', '0')
    client.set('longerCE01', '0')
    pass
    #run_cp('potentiostat01',-0.004,5)


