from typing import List, Any
from prefect import flow, get_run_logger
from prefect.variables import Variable

from ..config.config import CONNECTIONS_INFO, DEFAULT_CONFIG
from ..hardware.syringe_pumps import compartment_wash

@flow
def empty_compartments(
    exclude_vials: List[str] = None,
    **kwargs: Any,
    ) -> None:
    """
    Empties all the compartments that are currently filled.
    If exclude_vials is provided, the vials in the list will not be emptied.
    Accepted exclude_vials entries: 'WEvial', 'CEvial', 'AZvial'
    Args:
        exclude_vials (List[str]): List of vials to exclude from the emptying process
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    vials_to_empty = []
    logger = get_run_logger()
    for component in CONNECTIONS_INFO:
        if 'tecan' not in component and 'runze' not in component and 'syringe' not in component:
            continue

        valve_name = component.replace("tecan", "valve").replace("runze", "valve").replace("syringe", "valve")
        has_valve = valve_name in CONNECTIONS_INFO

        for port in CONNECTIONS_INFO[component]:
            if 'AZvial' in exclude_vials and 'AZ' in component:
                continue
            if 'AZ' in component and ('WE' in port or 'CE' in port):
                continue
            for port in CONNECTIONS_INFO[component]:
                if 'vial' in port:
                    if ('WEvial' in port and 'WEvial' in exclude_vials) or ('CEvial' in port and 'CEvial' in exclude_vials) or ('AZvial' in port and 'AZvial' in exclude_vials):
                        continue
                    compartment_info = Variable.get(str(port).lower())
                    if compartment_info['volume'] > 0:
                        vials_to_empty.append((port, component))
                        logger.info(f"Vial {port} will be emptied from compartment {component}")
        if has_valve:
            if 'AZvial' in exclude_vials and 'AZ' in component:
                continue
            for port in CONNECTIONS_INFO[valve_name]:
                if 'vial' in port:
                    if ('WEvial' in port and 'WEvial' in exclude_vials) or ('CEvial' in port and 'CEvial' in exclude_vials):
                        continue
                    compartment_info = Variable.get(str(port).lower())
                    if compartment_info['volume'] > 0:
                        vials_to_empty.append((port, component))
                        logger.info(f"Vial {port} will be emptied from compartment {component}")

    for vial in vials_to_empty:
        if 'AZ' in vial[1]:
            repeats = config['wash_vial_repeats']
            wash_vol = config['wash_vial_volume']
            speed = config['wash_vial_speed']
            speed_last_empty = config['wash_vial_last_empty']
        else:
            repeats = config['wash_flow_cell_wash_comp_repeats']
            wash_vol = config['wash_flow_cell_wash_comp_volume']
            speed = config['wash_flow_cell_wash_comp_speed']
            speed_last_empty = config['wash_flow_cell_wash_comp_speed_last_empty']

        compartment_wash(syringe_pump=vial[1], compartment=vial[0], repeats=repeats, 
                wash_vol=wash_vol, speed=speed, speed_last_empty=speed_last_empty, **kwargs)
        logger.info(f"Vial {vial[0]} connected to {vial[1]} has been emptied")


@flow
def main():
    empty_compartments(exclude_vials=['WEvial', 'CEvial'])


