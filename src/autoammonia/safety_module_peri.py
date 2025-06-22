import time
from prefect import flow
from typing import Any, Optional
import traceback
from pathlib import Path

from .config.config import DEFAULT_CONFIG, CONFIG_COMPONENTS
from .utils.redis_client import client
from .hardware.peristaltic_pumps import run_pump, check_pump
from .reaction_steps import empty_and_stop_pumps


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
            actual_status = check_pump(pump=pump, **kwargs)
            if actual_status != expected_status:
                time.sleep(5)
                expected_status = float(client.get(name=pump))
                direction = True if float(expected_status) > 0 else False
                speed = abs(float(expected_status))
                run_pump(pump=pump,speed=speed,direction=direction,**kwargs)
                actual_status = check_pump(pump)
                if actual_status != expected_status:
                    client.set(name='safe_operation',value=0)
        time.sleep(15)

@flow
def track_safety(
        emergency_stop_retries: Optional[int] = None, 
        emergency_stop_retries_delay: Optional[float] = None,
        **kwargs: Any
)->None:
    """
    Activates emergency procedures when safe operation is compromised, ensuring the flow cells are emptied
    and cleaned to avoid contamination.

    Args:
        emergency_stop_retries (Optional[int]): Number of times it will try to wash the cells when safety
            operation flag is triggered. Defaults to config['emergency_stop_retries'].
        emergency_stop_retries_delay (Optional[float]): Delay in seconds between each retry attempt
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    
    emergency_stop_retries = emergency_stop_retries if emergency_stop_retries is not None else config['emergency_stop_retries']
    emergency_stop_retries_delay = emergency_stop_retries_delay if emergency_stop_retries_delay is not None else config[
        'emergency_stop_retries_delay']
    parallel_cells = config['parallel_cells']
    
    safe_operation = False
    while True:
        if client.get(name='safety_operation')=='0':
            for _ in range(emergency_stop_retries):
                try:
                    empty_and_stop_pumps(wash_time=config['wash_flow_cell_time'],
                                         pump_speed=config['wash_flow_cell_speed'],
                                         retries=config['longer_retries_emergency_stop'],
                                         retries_delay=config['longer_retries_delay_emergency_stop'])
                    print('An error happened, flow cell emptied and cleaned without problems')
                    
                    break
                except Exception as e:
                    print(f'An error occurred: {e}')
                    traceback.print_exc()
                    safe_operation = True
                time.sleep(emergency_stop_retries_delay)
            if not safe_operation:
                print(f'Warning, an error happened, flow cell could not be cleaned properly after {emergency_stop_retries} retries.')
                for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
                    status = client.get(f'flow_cell{cell_str}_content')
                    print(f'flow_cell{cell_str} content is {status}')
                break

        time.sleep(30)
        
        
def safety_module_deploy():
    track_safety.from_source(
        source=Path(__file__).parent,
        entrypoint=f"safety_module_peri.py:track_safety",
    ).deploy(
        name="safety_module_flow",
        work_pool_name="safety_module_pool",
    )