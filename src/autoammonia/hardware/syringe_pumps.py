import time
from math import ceil
from typing import Union, Optional, Any, List, Tuple

from prefect import task, flow, get_run_logger
from prefect.variables import Variable

from ..utils.redis_client import client
from ..utils.decorators import run_on_component, with_lock
from ..config.config import DEFAULT_CONFIG, CONNECTIONS_INFO
from ..config.components_config import CONFIG_COMPONENTS
from .selection_valves import switch_port_valve


@task
@run_on_component()
def syringe_draw(
        syringe_pump: str,
        volume: float,
        valve_port: Union[str, int],
        speed: float,
        fail_retries: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Draws a specified volume of liquid from a syringe pump. If the draw operation fails,
    attempts to dispense the syringe content to waste. If the waste dispensing succeeds, 
    raises an error to indicate the primary operation failed. If both fail, raises
    an error to indicate a continuous failure, and the flag 'safety_operation' is set to 
    0 in redis, which will trigger the emergency_stop function.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to draw (in mL).
        valve_port (Union[str, int]): Identifier of the valve port to be used for drawing liquid.
        speed (float): The drawing speed to be set temporarily (in mL/s).
        fail_retries (Optional[int]): Number of attempts to dispense the syringe content
            to waste in case of an error. Defaults to config['syringe_fail_retrials'].
        **kwargs (Any): Additional configuration options.

    Raises:
        RuntimeError: If the draw operation fails, or if the syringe cannot be emptied to waste.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    fail_retries = fail_retries if fail_retries is not None else config['syringe_fail_retrials']
    
    logger = get_run_logger()
    try:
        syringe_pump.draw(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as draw_error:
        for trial in range(1,fail_retries+1):
            try:
                syringe_pump.dispense_all(valve_port='waste', speed=speed)
                logger.warning(f'[{syringe_pump}] Syringe content dispensed successfully to waste')
                raise RuntimeError(f'[{syringe_pump}] Syringe content dispensed successfully to waste') from draw_error
            except Exception as dispense_error:
                logger.warning(f"[{syringe_pump}] Attempt {trial} to dispense syringe to waste failed: {dispense_error}")
        raise RuntimeError(
            f"Unable to draw volume from valve port '{valve_port}' or empty the syringe to waste "
            f"after {fail_retries} retries."
        ) from draw_error


@task
@run_on_component()
def syringe_dispense(
        syringe_pump: str,
        volume: float,
        valve_port: Union[str, int],
        speed: float,
        fail_retries: Optional[int] = None,
        **kwargs: Any,
) -> None:
    """
    Dispenses a specified volume of liquid using a syringe pump. If the dispensing operation fails,
    attempts to dispense the syringe content to waste. If the waste dispensing succeeds, raises an error
    to indicate the primary operation failed. If both fail, raises an error and sets the flag 'safety_operation'
    to 0 in redis to trigger an emergency stop.

    Args:
        syringe_pump (str): The syringe pump to use.
        volume (float): The volume of liquid to dispense (in mL).
        valve_port (Union[str, int]): Identifier of the valve port to be used for dispensing liquid.
        speed (float): The dispensing speed to be set temporarily (in mL/s).
        fail_retries (Optional[int]): Number of attempts to dispense the syringe content
            to waste in case of an error. Defaults to config['syringe_fail_retrials'].
        **kwargs (Any): Additional configuration options.

    Raises:
        RuntimeError: If the draw operation fails, or if the syringe cannot be emptied to waste.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    fail_retries = fail_retries if fail_retries is not None else config['syringe_fail_retrials']
    
    logger = get_run_logger()
    try:
        syringe_pump.dispense(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as dispense_error:
        for trial in range(1, fail_retries + 1):
            try:
                syringe_pump.dispense_all(valve_port='waste', speed=speed)
                logger.warning(f'[{syringe_pump}] Syringe content dispensed successfully to waste')
                raise RuntimeError(f'Syringe content dispensed successfully to waste') from dispense_error
            except Exception as waste_error:
                logger.warning(f"[{syringe_pump}] Attempt {trial} to dispense syringe to waste failed: {waste_error}")
        raise RuntimeError(
            f"Unable to dispense volume to valve port '{valve_port}' or empty the syringe to waste "
            f"after {fail_retries} retries."
        ) from dispense_error



@flow
def syringe_draw_and_dispense(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        **kwargs,
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
        **kwargs (Any): Additional configuration options.

    Notes:
        - This function is only meant to be used in draw_and_dispense_tecan. Use carefully at other contexts.
        - It only draws and dispenses a specific amount from one port to the other. But should not be used for
          specific volume transfer between vessels.
    """

    if volume > 0:
        syringe_draw(syringe_pump=syringe_pump, volume=volume, valve_port=draw_valve_port, speed=speed, **kwargs)
        time.sleep(wait)
        syringe_dispense(syringe_pump=syringe_pump, volume=volume, valve_port=dispense_valve_port, speed=speed, **kwargs)
        time.sleep(wait)
    else:
        logger = get_run_logger()
        logger.warning(f"[{syringe_pump}] Attempt to draw and dispense {volume} mL from {draw_valve_port} to {dispense_valve_port}. Skipping operation as volume is 0.")


@flow
def syringe_draw_and_dispense_volume(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        retries: Optional[int] = None,
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

    Behavior:
        - If the specified `volume` exceeds the syringe's maximum capacity, the function splits the operation
          into smaller iterations. Each iteration processes a portion of the total volume, calculated as
          `volume / dispense_iterations`.
        - Each iteration performs a call to `raw_and_dispense_tecan_func` with the calculated `volume_per_iteration`.
        - Retry logic is applied to each iteration individually, using the specified `retries`.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['draw_and_dispense_retries']
    
    logger = get_run_logger()

    dispense_iterations = ceil(volume / (1e3 * CONFIG_COMPONENTS[syringe_pump]["syringe_volume"]))
    volume_per_iteration = volume / dispense_iterations if dispense_iterations > 0 else 0
    if volume_per_iteration > 0:
        for i in range(0, dispense_iterations):
            syringe_draw_and_dispense.with_options(
                retries=retries,
            )(syringe_pump=syringe_pump, volume=volume_per_iteration, draw_valve_port=draw_valve_port,
              dispense_valve_port=dispense_valve_port, speed=speed, wait=wait, **kwargs)
    else:
        logger.warning(f"[{syringe_pump}] Attempt to draw and dispense {volume} mL from {draw_valve_port} to {dispense_valve_port}. Skipping operation as volume is 0.")


def get_connected_port(
    syringe_pump: str,
    port: Union[str, int],
    connection_info: dict
) -> Tuple[Optional[Union[str, int]], Optional[Union[str, int]]]:
    """
    Returns a tuple (main_port, sub_port):
      - If port is directly on syringe_pump, returns (port, None)
      - If port is found on a valve connected to syringe_pump, returns (valve_name, port)
      - If not found, returns (None, None)
    """
    if port in connection_info[syringe_pump]:
        return port, None
    valve = None
    for syringe_port in connection_info[syringe_pump]:
        if 'valve' in syringe_port:
            valve = syringe_port
            if port in connection_info[syringe_port]:
                return syringe_port, port
    logger = get_run_logger()
    logger.error(f"Port {port} not found in syringe pump {syringe_pump} connections.")
    logger.error(f"Available ports in syringe: {list(connection_info[syringe_pump].keys())}")
    if valve is not None:
        logger.error(f"Available ports in valve {valve}: {list(connection_info[valve].keys())}")
    else:
        logger.error("No valve found in syringe pump connections.")
    raise ValueError('Port not found in syringe pump connections. Please check the configuration.')


def get_air_volume(
        syringe_pump: str,
        syringe_port: Union[str, int, None],
        valve_port: Union[str, int, None],
        connections_info: dict,
        air_compensation_volume: Optional[float] = None
) -> float:
    """
    Calculates the volume of air to be drawn from the syringe pump or valve port.
    This function checks if the specified port is connected to a stock solution or not.
    If it is not connected to a stock solution, it calculates the air volume based on the
    volume of the syringe and the valve port, if applicable. If it is connected to a stock solution,
    it returns 0, indicating no air volume needs to be drawn.
    
    Args:
        syringe_pump (str): The syringe pump identifier.
        syringe_port (Union[str, int, None]): The port identifier for the syringe.
        valve_port (Union[str, int, None]): The port identifier for the valve, if applicable.
        connections_info (dict): Dictionary containing connection information for the syringe pump and ports.
        air_compensation_volume (Optional[float]): Additional volume to account for air in the tubing.
    
    Returns:
        float: The calculated air volume to be drawn, or 0 if the port is connected to a stock solution.
    """
    if valve_port is not None:
        air_volume = connections_info[syringe_pump][syringe_port]['con_vol']
        if str(connections_info[syringe_port][valve_port]['usage']).lower() != 'stock':  
            # If it's not a stock solution, also need to drawn volume valve-compartment
            air_volume += connections_info[syringe_port][valve_port]['con_vol']
        air_volume += air_compensation_volume
    else:
        if str(connections_info[syringe_pump][syringe_port]['usage']).lower() != 'stock':
            air_volume = connections_info[syringe_pump][syringe_port]['con_vol']
        else:
            return 0.
    return air_volume
        

@flow
def syringe_transfer_unlocked(
        syringe_pump: str,
        volume: float,
        draw_valve_port: Union[int, str],
        dispense_valve_port: Union[int, str],
        speed: float,
        wait: Optional[float] = 0,
        air_compensation_volume: Optional[float] = None,
        air_flush_factor: Optional[int] = None,
        air_flush_speed: Optional[float] = None,
        safety_empty: Optional[bool] = False,
        **kwargs: Any,
) -> None:
    """
    Draws a specified volume of liquid from a designated valve port and dispenses it to a specified 
    valve port using a syringe pump. The operation ensures accurate volume transfer, accounting for air 
    compensation in the tubing. This process is independent of whether the valve is directly connected to 
    the syringe pump or through a selection valve. It does not generate a lock for the process.

    Args:
        syringe_pump (str): The identifier for the syringe pump to use. This could be a model or name used 
            to determine valve configurations.
        volume (float): The volume of liquid (in mL) to draw from the input valve port and dispense to the 
            output valve port.
        draw_valve_port (Union[int, str]): The port identifier to draw liquid from.
        dispense_valve_port (Union[int, str]): The port identifier to dispense liquid into.
        speed (float): The speed at which the liquid is drawn and dispensed (in mL/s).
        wait (Optional[float], default=0): Time (in seconds) to wait between drawing and dispensing. 
            This ensures that the syringe pump's movements are not rushed.
        air_compensation_volume (Optional[float]): Additional volume to account for air in the tubing, 
            ensuring that the liquid dispensed is accurate. Defaults to configuration value.
        air_flush_factor (Optional[int]): A factor to determine the extra air volume that should be 
            dispensed after the liquid volume. Defaults to configuration value.
        air_flush_speed (Optional[float]): The speed (in mL/s) used during air flushing to ensure the 
            accuracy of dispensing. Defaults to configuration value.
        **kwargs (Any): Additional keyword arguments that can override the default configuration settings.

    Behavior:
        - The function draws air from the input tubing if it is not connected to a stock solution and accounts 
          for this volume to ensure the liquid dispensed is accurate.
        - The `air_compensation_volume` is added to the drawn volume to ensure accuracy when dispensing liquid.
        - After drawing and dispensing the specified liquid volume, additional air volume is dispensed to ensure 
          that the liquid fully exits the syringe pump and tubing into the desired container.
        - If the valve is connected via a selection valve or directly to the pump, the appropriate port is selected 
          to draw and dispense liquid while ensuring that air is flushed appropriately.
        - If the port is connected via a selection valve, the function switches between valves as necessary.
        
        - Depending on the syringe_pump name, selects the valve corresponding to that syringe pump.
        - If the draw_valve_port is not a stock solution (and therefore tube is empty/full of air), it draws all the
          air in the tube, from it end to the syringe_pump, taking into account syringe to valve tube volume if needed.
          This is to make sure all volume subtracted in following operation is liquid, with no air contribution.
        - The `air_compensation_volume` is added to the drawn volume to ensure accuracy when dispensing liquid.
        - The volume specified is drawn and dispensed from draw_port_valve to dispense_port_valve, independently if
          those ports are connected directly to pump or through the corresponding valve.
        - After drawing and dispensing the specified liquid volume, additional air volume is dispensed to ensure 
          that the liquid fully exits the syringe pump and tubing into the desired container.

    Notes:
        - This function does not take into account cases in which both draw_port_valve and dispense_port_valve are
          connected to the valve instead of directly to the pump.
          Be careful and make sure at least one of them is connected directly to the pump.
    """

    config = {**DEFAULT_CONFIG, **kwargs}
    air_compensation_volume = air_compensation_volume if air_compensation_volume is not None else config[
        "air_compensation_volume"]
    air_flush_factor = air_flush_factor if air_flush_factor is not None else config["air_flush_factor"]
    air_flush_speed = air_flush_speed if air_flush_speed is not None else config["air_flush_speed"]
    
    logger = get_run_logger()
    if (dispense_valve_port != draw_valve_port) and (draw_valve_port != 'air'):
        draw_valve_port_info = Variable.get(str(draw_valve_port).lower())
        dispense_valve_port_info = Variable.get(str(dispense_valve_port).lower())
        if draw_valve_port_info['volume'] < volume and not safety_empty:
            logger.critical(f"[{syringe_pump}] Not enough volume in {draw_valve_port}")
            logger.error(f"[{draw_valve_port}] Current vol: {draw_valve_port_info['volume']}, trying to subtract: {volume}")
            raise ValueError(f"Not enough volume in {draw_valve_port} to perform draw_and_dispense_volume operation")
        if (dispense_valve_port_info['volume'] + volume) > dispense_valve_port_info['max_vol']:
            logger.critical(f"[{syringe_pump}] Not enough volume in {draw_valve_port}")
            logger.error(f"[{dispense_valve_port}] Current vol: {dispense_valve_port_info['volume']}, "
                         f"max. volume: {dispense_valve_port_info['max_vol']}, trying to add: {volume}")
            raise ValueError(f"Not enough capacity in {dispense_valve_port} to receive volume")
        
    #Look for where the draw_port and dispense ports are, if either in the pump or in any of the valves connected to it, 
    # and switch valves accordingly.
    syringe_port_input, valve_port_input = get_connected_port(syringe_pump, draw_valve_port, CONNECTIONS_INFO)
    syringe_port_output, valve_port_output = get_connected_port(syringe_pump, dispense_valve_port, CONNECTIONS_INFO)
    if valve_port_input: 
        switch_port_valve(valve=syringe_port_input, port=valve_port_input, **kwargs)
        logger.info(f"[syringe_transfer_unlocked] Draw port in {syringe_port_input}, valved switched to {valve_port_input}")
    if valve_port_output: 
        switch_port_valve(valve=syringe_port_output, port=valve_port_output, **kwargs)
        logger.info(
            f"[syringe_transfer_unlocked] Dispense port in {syringe_port_output}, valved switched to {valve_port_output}")
    

    # Draw and dispense the required air from the input tube if needed
    input_air_volume = get_air_volume(syringe_pump, syringe_port_input, valve_port_input, 
                                      CONNECTIONS_INFO, air_compensation_volume)
    if input_air_volume > 0:
        syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=input_air_volume,
                                         draw_valve_port=syringe_port_input, dispense_valve_port='waste', 
                                         speed=air_flush_speed, **kwargs)
        logger.info(f"[syringe_transfer_unlocked] Subtracted {input_air_volume} mL of dead volume from {syringe_port_input}.")

    # Draw/Dispense liquid + air
    air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
    syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=volume, draw_valve_port=syringe_port_input,
                                     dispense_valve_port=syringe_port_output, wait=wait, speed=speed, **kwargs)
    logger.info(f"[syringe_transfer_unlocked] Transferred {volume} mL from {syringe_port_input} to {syringe_port_output}")
    syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                     dispense_valve_port=syringe_port_output, wait=wait, speed=air_flush_speed, **kwargs)
    logger.info(
        f"[syringe_transfer_unlocked] Transferred completed, {volume} mL of air transferred to {syringe_port_output}")
    if input_air_volume > 0:  # If the drawing port does not come from a stock solution, we want to leave it empty
        syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                         dispense_valve_port=syringe_port_input, wait=wait, speed=air_flush_speed, **kwargs)
        logger.info(f"[syringe_transfer_unlocked] Recovered {input_air_volume} mL of dead volume to {syringe_port_input}.")
    logger.info(f"[syringe_transfer_unlocked] Full transfer completed with {syringe_pump}: {volume} mL from {draw_valve_port} to {dispense_valve_port} ports")
    if (dispense_valve_port != draw_valve_port) and (draw_valve_port != 'air'):
        draw_valve_port_info['volume'] = max(draw_valve_port_info['volume'] - volume, 0)
        dispense_valve_port_info['volume'] += volume
        Variable.set(str(draw_valve_port).lower(), draw_valve_port_info, overwrite=True)
        logger.info(f"[syringe_transfer_unlocked] Updated info on {draw_valve_port}: {draw_valve_port_info}")
        Variable.set(str(dispense_valve_port).lower(), dispense_valve_port_info, overwrite=True)
        logger.info(f"[syringe_transfer_unlocked] Updated info on {dispense_valve_port}: {dispense_valve_port_info}")


@flow
def syringe_wash_unlocked(
        syringe_pump: str,
        repeats: int,
        wash_vol: float,
        speed: float,
        wash_valves: List[str],
        air_flush_factor: Optional[int] = None,
        air_flush_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Washes the syringe a specified number of times with the given volume and speed. If specified, also washes the
    valve associated with the pump.
    It does not generate a lock for the process

    Args:
        syringe_pump (str): The syringe pump to use for washing. This can be the pump's model or name.
        repeats (int): The number of washing cycles to perform.
        wash_vol (float): The volume (in mL) of liquid to use for each wash cycle.
        speed (float): The speed of the syringe during washing (in mL/s).
        wash_valves (bool): Whether to wash the valve associated with the syringe pump.
        air_flush_factor (Optional[int]): The factor to determine the volume of air to flush through the system 
            after the washing process. Defaults to the configuration value if not provided.
        air_flush_speed (Optional[float]): The speed (in mL/s) at which the air is flushed through the system 
            to clear residual liquid. Defaults to the configuration value if not provided.
        **kwargs (Any): Additional keyword arguments to override the default configuration settings.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    air_flush_factor = air_flush_factor if air_flush_factor is not None else config['air_flush_factor']
    air_flush_speed = air_flush_speed if air_flush_speed is not None else config["air_flush_speed"]
    
    logger = get_run_logger()
    # Syringe washing
    for _ in range(repeats):
        syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                         dispense_valve_port='waste', speed=speed, **kwargs)
    logger.info(f"[syringe_wash_unlocked] Syringe {syringe_pump} washed with {wash_vol} mL of water {repeats} times")
    
    # Valve washing
    if len(wash_valves)>0:
        for syringe_valve in wash_valves:
            switch_port_valve(valve=syringe_valve, port='waste', **kwargs)
    
            air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                             dispense_valve_port=syringe_valve, speed=speed, **kwargs)
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                             dispense_valve_port=syringe_valve, speed=air_flush_speed, **kwargs)
            logger.info(f"[syringe_wash_unlocked] Valve {syringe_valve} washed with {wash_vol} of water")

@flow
@with_lock()
def syringe_transfer_and_wash(
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
    logger = get_run_logger()

    # Use provided arguments or fall back to default config
    wash_repeats = wash_repeats if wash_repeats is not None else config['syringe_wash_repeats']
    wash_speed = wash_speed if wash_speed is not None else config['syringe_wash_speed']
    if wash_vol is not None:
        wash_vol = wash_vol
    else:
        wash_vol = config['syringe_wash_volume_RX'] if 'RX' in syringe_pump else config['syringe_wash_volume_AZ']

    syringe_transfer_unlocked(
        syringe_pump=syringe_pump, volume=volume, draw_valve_port=draw_valve_port,
        dispense_valve_port=dispense_valve_port, speed=speed, wait=wait, **kwargs,
    )
    logger.info(f"[Syringe_transfer_and_wash] Transferred {volume} mL from {draw_valve_port} to {dispense_valve_port}.")
    
    #Check if valves were used in draw or dispense
    wash_valves = []
    syringe_port_input, valve_port_input = get_connected_port(syringe_pump, draw_valve_port, CONNECTIONS_INFO)
    syringe_port_output, valve_port_output = get_connected_port(syringe_pump, dispense_valve_port, CONNECTIONS_INFO)
    wash_valves = wash_valves + [syringe_port_input,] if valve_port_input else wash_valves
    wash_valves = wash_valves + [syringe_port_output,] if valve_port_output else wash_valves
                    
    syringe_wash_unlocked(syringe_pump=syringe_pump, repeats=wash_repeats, wash_vol=wash_vol, speed=wash_speed,
                          wash_valves=wash_valves, **kwargs)
    logger.info(f"[Syringe_transfer_and_wash] Valves washed: {wash_valves}")


@flow
@with_lock()
def syringe_transfer_uvvis_and_wash(
        syringe_pump: str,
        aliquot_volume: float,
        draw_valve_port: Union[int, str],
        speed: float | int | None,
        wash_repeats: Optional[int] = None,
        wash_vol: Optional[float] = None,
        wash_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Transfers an aliquot volume from a draw valve port to the UV-VIS compartment.
    It dispenses air in the tubo leading to the UV-VIS, to ensure aliquot reached
    the UV-VIS cuvette.
    It washes the valves used in the transfer.
    Args:
        syringe_pump (str): The syringe pump to use.
        aliquot_volume (float): The volume of the aliquot to transfer (in mL).
        draw_valve_port (Union[int, str]): The valve port for drawing the aliquot.
        speed (float | int | None): The speed to draw the aliquot (in mL/s). Defaults to config['aliquot_filling_speed'].
        wash_repeats (Optional[int]): Number of washing cycles. Defaults to config['syringe_wash_repeats'].
        wash_vol (Optional[float]): Volume (in mL) to wash with. Defaults to config['syringe_wash_volume_RX'] or
                                    config['syringe_wash_volume_AZ'] depending on specified syringe pump.
        wash_speed (Optional[float]): Speed of the syringe during washing (in mL/s). Defaults to config['syringe_wash_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    speed = speed if speed is not None else config['aliquot_filling_speed']
    # Use provided arguments or fall back to default config
    wash_repeats = wash_repeats if wash_repeats is not None else config['syringe_wash_repeats']
    wash_speed = wash_speed if wash_speed is not None else config['syringe_wash_speed']
    if wash_vol is not None:
        wash_vol = wash_vol
    else:
        wash_vol = config['syringe_wash_volume_RX'] if 'RX' in syringe_pump else config['syringe_wash_volume_AZ']
    logger = get_run_logger()

    syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=aliquot_volume, draw_valve_port=draw_valve_port,
                              dispense_valve_port='uv_vis', air_flush_factor=0, speed=speed, **kwargs)
    logger.info(f"[Syringe_transfer_uvvis] Transferred {aliquot_volume} mL from {draw_valve_port} to UV-VIS.")
    tube_volume = CONNECTIONS_INFO[syringe_pump]['uv_vis']['con_vol']
    if aliquot_volume < tube_volume:
        extra_air_volume = tube_volume - aliquot_volume
        syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=extra_air_volume, draw_valve_port='air',
                                  dispense_valve_port='uv_vis', speed=speed, **kwargs)
        logger.info(f"[Syringe_transfer_uvvis] Transferred {extra_air_volume} mL of air to UV-VIS.")
    
    #Check if valves were used in draw or dispense
    wash_valves = []
    syringe_port_input, valve_port_input = get_connected_port(syringe_pump, draw_valve_port, CONNECTIONS_INFO)
    syringe_port_output, valve_port_output = get_connected_port(syringe_pump, 'uv_vis', CONNECTIONS_INFO)
    wash_valves = wash_valves + [syringe_port_input,] if valve_port_input else wash_valves
    wash_valves = wash_valves + [syringe_port_output,] if valve_port_output else wash_valves

    syringe_wash_unlocked(syringe_pump=syringe_pump, repeats=wash_repeats, wash_vol=wash_vol, speed=wash_speed,
                          wash_valves=wash_valves, **kwargs)
    logger.info(f"[Syringe_transfer_uvvis_and_wash] Valves washed: {wash_valves}")


@flow
@with_lock()
def compartment_wash(
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
    
    logger = get_run_logger()
    compartment_info = Variable.get(str(compartment).lower())
    volume = compartment_info['volume']

    syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=volume, draw_valve_port=compartment,
                              dispense_valve_port='waste', speed=speed, **kwargs)
    logger.info(f"[Compartment_wash] Compartment {compartment} emptied")
    client.set(compartment + '_volume', 0)

    for _ in range(repeats):
        syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                  dispense_valve_port=compartment, speed=speed, **kwargs)
        logger.info(f"[Compartment_wash] Compartment {compartment} filled with water. Repeat: {_}")
        syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port=compartment,
                                  dispense_valve_port='waste', speed=speed, **kwargs)
        logger.info(f"[Compartment_wash] Compartment {compartment} emptied. Repeat: {_}")
    syringe_transfer_unlocked(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port=compartment,
                              dispense_valve_port='waste', speed=speed_last_empty, safety_empty=True, **kwargs)
    logger.info(f"[{syringe_pump}] Compartment '{compartment}' washed {repeats} times with {wash_vol} mL at {speed} mL/s. ")


@flow
@with_lock()
def compartment_wash_uvvis(
        syringe_pump: str,
        repeats: Optional[int] = None,
        wash_vol: Optional[float] = None,
        speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Washes the specified compartment. Designed for washing 'WE/CE_vial' or 'vials'

    Args:
        syringe_pump (str): Syringe pump to use.
        repeats (Optional[int]): Number of wash cycles. Defaults to config['wash_compartment_repeats'].
        wash_vol (Optional[float]): Volume of water for each wash step (in mL). Defaults to config['wash_compartment_volume'].
        speed (Optional[float]): Draw/dispense speed (in mL/s). Defaults to config['wash_compartment_speed'].
        speed_last_empty (Optional[float]): Speed for the final emptying step (in mL/s). Defaults to config['wash_compartment_speed_last_empty'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    repeats = repeats if repeats is not None else config['wash_uvvis_repeats']
    wash_vol = wash_vol if wash_vol is not None else config['uv_vis_wash_volume']
    speed = speed if speed is not None else config['uv_vis_wash_speed']
    
    logger = get_run_logger()

    for _ in range(repeats):
        syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                dispense_valve_port='UV_VIS', speed=speed, **kwargs)
        logger.info(f"[Compartment_wash_uvvis] UV-VIS flow cell washed with water. Repeat: {_}")
    air_flush_volume = CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
    for _ in range(2):
        syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                dispense_valve_port='UV_VIS', speed=speed, **kwargs)
        logger.info(f"[Compartment_wash_uvvis] Air flushed to UV-VIS flow cell. Repeat: {_}")


@flow
def compartment_fill(
        syringe_pump: str,
        source: str,
        destination: str,
        volume: float,
        speed: float,
        **kwargs: Any,
) -> None:
    """
    Transfers liquid from one compartment to another using a syringe pump and updates destination compartment volume accordingly

    Args:
        syringe_pump (str): The syringe pump to use for the transfer.
        source (str): The name of the source compartment from which the liquid will be transferred.
        destination (str): The name of the destination compartment to which the liquid will be transferred.
        volume (float): The amount of liquid to transfer (in mL).
        speed (float): The speed at which the liquid is transferred (in mL/s).
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    logger = get_run_logger()
    syringe_transfer_and_wash(
        syringe_pump=syringe_pump, volume=volume, draw_valve_port=source,
        dispense_valve_port=destination, speed=speed, **kwargs
    )
    client.set(f"{destination}_volume", volume)
    logger.info(f"[compartment_fill] Transferred {volume} mL from {source} to {destination}.")
    # client.set(f"{source}_volume", float(client.get(f"{source}_volume"))-volume)
