import time
from math import ceil
from typing import Union, Optional, Any

from mako.exceptions import RuntimeException
from prefect import task, flow

from redis_client import client
from decorators import run_on_component, with_lock
from default_config import DEFAULT_CONFIG, CONNECTIONS_INFO, CONFIG_COMPONENTS
from valco_valve import switch_port_valve


@task
@run_on_component()
def draw_tecan_func(
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
    
    try:
        syringe_pump.draw(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as draw_error:
        for trial in range(1,fail_retries+1):
            try:
                syringe_pump.dispense_all(valve_port='waste', speed=speed)
                raise RuntimeException(f'Syringe content dispensed successfully to waste') from draw_error
            except Exception as dispense_error:
                print(f"Attempt {trial} to dispense syringe to waste failed: {dispense_error}")
        raise RuntimeError(
            f"Unable to draw volume from valve port '{valve_port}' or empty the syringe to waste "
            f"after {fail_retries} retries."
        ) from draw_error


@task
@run_on_component()
def dispense_tecan_func(
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
    
    try:
        syringe_pump.dispense(volume=volume, valve_port=valve_port, speed=speed)
    except Exception as dispense_error:
        for trial in range(1, fail_retries + 1):
            try:
                syringe_pump.dispense_all(valve_port='waste', speed=speed)
                raise RuntimeError(f'Syringe content dispensed successfully to waste') from dispense_error
            except Exception as waste_error:
                print(f"Attempt {trial} to dispense syringe to waste failed: {waste_error}")
        raise RuntimeError(
            f"Unable to dispense volume to valve port '{valve_port}' or empty the syringe to waste "
            f"after {fail_retries} retries."
        ) from dispense_error



@flow
def draw_and_dispense_tecan_func(
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
    draw_tecan_func(syringe_pump=syringe_pump, volume=volume, valve_port=draw_valve_port, speed=speed, **kwargs)
    time.sleep(wait)
    dispense_tecan_func(syringe_pump=syringe_pump, volume=volume, valve_port=dispense_valve_port, speed=speed, **kwargs)
    time.sleep(wait)


@flow
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
    config = {**DEFAULT_CONFIG, **kwargs}
    retries = retries if retries is not None else config['draw_and_dispense_retries']
    retries_delay = retries_delay if retries_delay is not None else config['draw_and_dispense_retries_delay']

    dispense_iterations = ceil(volume / (1e3 * syringe_pump.syringe_volume))
    volume_per_iteration = volume / dispense_iterations

    for i in range(0, dispense_iterations):
        draw_and_dispense_tecan_func.with_options(
            retries=retries,
            retry_delay_seconds=retries_delay
        )(syringe_pump=syringe_pump, volume=volume_per_iteration, draw_valve_port=draw_valve_port,
          dispense_valve_port=dispense_valve_port, speed=speed, wait=wait, **kwargs)


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

    # Select valve according to the pump type
    if 'RX' in syringe_pump.upper():
        syringe_valve = 'valveRX' + syringe_pump[-2:]
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]

    # Draw and dispense the required air from the input tube if needed
    input_air_volume = 0
    if draw_valve_port in CONNECTIONS_INFO[syringe_pump]:
        if CONNECTIONS_INFO[syringe_pump][draw_valve_port][
            'usage'].lower() != 'stock':  # If is not a stock solution, tube is empty and air must be drawn before
            input_air_volume = CONNECTIONS_INFO[syringe_pump][draw_valve_port]['volume']
            input_air_volume = input_air_volume + air_compensation_volume
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_air_volume,
                                    draw_valve_port=draw_valve_port, dispense_valve_port='air_waste', **kwargs)
    else:
        input_air_volume = CONNECTIONS_INFO[syringe_pump]["valve"][
            'volume']  # Tube pump-valve will always be empty and air need to be drawn
        if CONNECTIONS_INFO[syringe_pump][draw_valve_port][
            'usage'].lower() != 'stock':  # If it's not a stock solution, also need to drawn volume valve-compartment
            input_air_volume += CONNECTIONS_INFO[syringe_valve][draw_valve_port]['volume']
        input_air_volume = input_air_volume + air_compensation_volume

        switch_port_valve(valve=syringe_valve, port=draw_valve_port, **kwargs)
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_air_volume,
                                draw_valve_port='valve', dispense_valve_port='air_waste', **kwargs)

    # Draw/Dispense liquid + air if needed 
    air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
    if (draw_valve_port in CONNECTIONS_INFO[syringe_pump]) and (dispense_valve_port in CONNECTIONS_INFO[syringe_pump]):
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=volume, draw_valve_port=draw_valve_port,
                                dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                dispense_valve_port=dispense_valve_port, wait=wait, speed=speed, **kwargs)
        if input_air_volume > 0:  # If the drawing port does not come from a stock solution, we want to leave it empty
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                    dispense_valve_port=dispense_valve_port, wait=wait, speed=air_flush_speed, **kwargs)
    else:
        if draw_valve_port in CONNECTIONS_INFO[syringe_pump]:
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=volume, draw_valve_port=draw_valve_port,
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
                                        dispense_valve_port=dispense_valve_port, wait=wait, speed=air_flush_speed,
                                        **kwargs)


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
        syringe_pump (str): The syringe pump to use for washing. This can be the pump's model or name.
        repeats (int): The number of washing cycles to perform.
        wash_vol (float): The volume (in mL) of liquid to use for each wash cycle.
        speed (float): The speed of the syringe during washing (in mL/s).
        wash_valve (bool): Whether to wash the valve associated with the syringe pump.
        air_flush_factor (Optional[int]): The factor to determine the volume of air to flush through the system 
            after the washing process. Defaults to the configuration value if not provided.
        air_flush_speed (Optional[float]): The speed (in mL/s) at which the air is flushed through the system 
            to clear residual liquid. Defaults to the configuration value if not provided.
        **kwargs (Any): Additional keyword arguments to override the default configuration settings.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    air_flush_factor = air_flush_factor if air_flush_factor is not None else config['air_flush_factor']
    air_flush_speed = air_flush_speed if air_flush_speed is not None else config["air_flush_speed"]

    # Syringe washing
    for _ in range(repeats):
        draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=wash_vol, draw_valve_port='water',
                                dispense_valve_port='air_waste', speed=speed, **kwargs)

    # Valve washing
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
    if (draw_valve_port not in DEFAULT_CONFIG[syringe_pump]['ports']) or (
            dispense_valve_port not in DEFAULT_CONFIG[syringe_pump]['ports']):
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

    if 'RX' in syringe_pump:  # Take volume in the compartment
        volume = float(client.get(f"{compartment}_volume"))
    else:  # If it's a vial, just take the full volume inside vial
        volume = config['vial_full_volume']

    draw_and_dispense_tecan_unlocked(syringe_pump=syringe_pump, volume=volume, draw_valve_port=compartment,
                                     dispense_valve_port='air_waste', speed=speed, **kwargs)
    client.set(compartment + '_volume', 0)

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
        dispense_valve_port=destination, speed=pump_speed, **kwargs
    )
    client.set(f"{destination}_volume", client.get(f"{source}_volume"))
    # client.set(f"{source}_volume", float(client.get(f"{source}_volume"))-volume)