import asyncio
import time
import json
from typing import Optional, List, Any, Tuple, Union
from prefect import flow
from pathlib import Path

from autoammonia.db.db_functions import add_experiment_to_db
from autoammonia.utils.files import get_default_folder
from .config.config import DEFAULT_CONFIG, CONNECTIONS_INFO,CONFIG_COMPONENTS

from .utils.redis_client import client
from .utils.elytes_precursors import reset_cache, get_valid_precursors, get_valid_electrolytes
from .hardware.selection_valves import switch_port_valve
from .hardware.potentiostat import run_method_parallel
from .hardware.peristaltic_pumps import run_pump, stop_pump
from .hardware.syringe_pumps import syringe_draw_and_dispense_volume, compartment_fill, syringe_wash_unlocked, compartment_wash, syringe_transfer_and_wash

from .utils.decorators import with_lock

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
        wash_vol = config['syringe_wash_volume_RX']
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]
        wash_vol = config['syringe_wash_volume_AZ']

    # Filling of all the stock solution tubes leading to the pump valve directly
    for port_name, port_info in CONNECTIONS_INFO[syringe_pump].items():
        if port_info['usage'].lower() == 'stock':
            input_tube_volume = port_info['volume']
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port=port_name,
                                             dispense_valve_port="waste", speed=speed, **kwargs)

    # Filling of al stock solution tubes leading to the valve assigned to the pump
    wash_valve = False
    for port_name, port_info in CONNECTIONS_INFO[syringe_valve].items():
        if port_info['usage'].lower() == 'stock':
            input_tube_volume = port_info['volume']
            switch_port_valve(valve=syringe_valve, port=port_name, **kwargs)
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port="valve",
                                             dispense_valve_port="waste", speed=speed, **kwargs)
            wash_valve = True

    syringe_wash_unlocked(syringe_pump, repeats=config['syringe_wash_repeats'], wash_vol=wash_vol,
                          speed=config['syringe_wash_speed'], wash_valve=wash_valve, **kwargs)

@flow
@with_lock()
def restore_pump(
        syringe_pump: str,
        **kwargs: Any,
) -> None:
    """
    This function empties the compartment-syringe/valve tube of liquid for all stock solution ports.

    Args:
        syringe_pump (str): The syringe pump to use.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    air_flush_speed = config["air_flush_speed"]
    air_flush_factor = config["air_flush_factor"]

    # Select valve according to the pump type
    if 'RX' in syringe_pump.upper():
        syringe_valve = 'valveRX' + syringe_pump[-2:]
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]

    # Empty of all the stock solution tubes leading to the pump valve directly
    air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
    for port_name, port_info in CONNECTIONS_INFO[syringe_pump].items():
        if port_info['usage'].lower() == 'stock':
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air',
                                             dispense_valve_port=port_name, speed=air_flush_speed, **kwargs)

    # Emptying of al stock solution tubes leading to the valve assigned to the pump
    for port_name, port_info in CONNECTIONS_INFO[syringe_valve].items():
        if port_info['usage'].lower() == 'stock':
            switch_port_valve(valve=syringe_valve, port=port_name, **kwargs)
            syringe_draw_and_dispense_volume(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port="air",
                                             dispense_valve_port="valve", speed=air_flush_speed, **kwargs)


@flow
def empty_and_stop_pumps(
        wash_time: float,
        pump_speed: float,
        **kwargs: Any,
) -> None:
    """
    Empties the flow cell after a process by running pumps in reverse to clear residues.

    Args:
        wash_time (float): Duration of the pump run in the reverse direction (seconds).
        pump_speed (float): Speed of the peristaltic pumps (rpm).
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    parallel_cells = config['parallel_cells']
    
    run_pump(pump='longerWE01', speed=pump_speed, direction=False, **kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, direction=False, **kwargs)
    time.sleep(wash_time)
    for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
        client.set(name=f'flow_cell{cell_str}_content',value='empty_contaminated')
    stop_pump(pump='longerWE01', **kwargs)
    stop_pump(pump='longerCE01', **kwargs)


@flow
def wash_flow_cell(
        repeats: Optional[int] = None,
        wash_time: Optional[float] = None,
        pump_speed: Optional[float] = None,
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
        pump_speed (Optional[float]): Pump speed during flushing (rpm). Defaults to config['wash_flow_cell_speed'].
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
    pump_speed = pump_speed if pump_speed is not None else config['wash_flow_cell_speed']
    filling_speed = filling_speed if filling_speed is not None else config['wash_flow_cell_filling_speed']
    wash_comp_repeats = wash_comp_repeats if wash_comp_repeats is not None else config['wash_flow_cell_wash_comp_repeats']
    wash_comp_volume = wash_comp_volume if wash_comp_volume is not None else config['wash_flow_cell_wash_comp_volume']
    wash_comp_speed = wash_comp_speed if wash_comp_speed is not None else config['wash_flow_cell_wash_comp_speed']
    wash_comp_speed_last_empty = wash_comp_speed_last_empty if wash_comp_speed_last_empty is not None else config['wash_flow_cell_wash_comp_speed_last_empty']
    parallel_cells = config['parallel_cells']

    empty_and_stop_pumps(wash_time=wash_time, pump_speed=pump_speed, **kwargs)

    for _ in range(repeats):
        for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
            compartment_fill(source='water', destination=f'WEvial{cell_str}', volume=wash_comp_volume, speed=filling_speed, **kwargs)
            compartment_fill(source='water', destination=f'CEvial{cell_str}', volume=wash_comp_volume, speed=filling_speed, **kwargs)
        run_pump(pump='longerWE01', speed=pump_speed, **kwargs)
        run_pump(pump='longerCE01', speed=pump_speed, **kwargs)
        for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
            client.set(name=f'flow_cell{cell_str}_content',value='water_contaminated')
        time.sleep(wash_time)
        for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
            compartment_wash(syringe_pump='tecanRX01', compartment=f'WEvial{cell_str}', repeats=wash_comp_repeats,
                             wash_vol=wash_comp_volume, pump_speed=wash_comp_speed,
                             pump_speed_last_empty=wash_comp_speed_last_empty, **kwargs)
            compartment_wash(syringe_pump='tecanRX01', compartment=f'CEvial{cell_str}', repeats=wash_comp_repeats,
                             wash_vol=wash_comp_volume, pump_speed=wash_comp_speed,
                             pump_speed_last_empty=wash_comp_speed_last_empty, **kwargs)

        empty_and_stop_pumps(wash_time=wash_time, pump_speed=pump_speed,**kwargs)
        
    for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
        client.set(name=f'flow_cell{cell_str}_content',value='clean')
        client.set(name=f'WEvial{cell_str}_volume', value=0)
        client.set(name=f'CEvial{cell_str}_volume', value=0)

@flow
def prepare_elyte_mix(
        syringe_pump: str,
        elyte_info: List[Tuple[str, float, Union[str, int]]],
        compartment: str,
        volume: float,
        filling_speed: Optional[float] = None,
        mixing_speed: Optional[float] = None,
        **kwargs: Any,
) -> None:
    """
    Prepares an electrolyte solution in the specified compartment given a ratio of electrolytes (elyte_ratios) and
    their corresponding ports (elyte_ports). Meant to be used for preparing the metal precursors mix for the
    electrodeposition step, and the electrolyte mix in the reaction step.

    Args:
        syringe_pump (str): Identifier for the syringe pump to use.
        elyte_info (List[Tuple[str, float, Union[str, int]]]): List of tuples with structure (compound, ratio, port).
        compartment (str): Compartment where the electrolyte mix will be dispensed.
        volume (float): Total volume of solution to prepare (mL). Defaults to config['electrodeposition_deposition_volume'].
        filling_speed (Optional[float]): Draw/dispense speed (mL/s). Defaults to config['electrodeposition_filling_speed'].
        mixing_speed (Optional[float]): Dispense speed during mixing (mL/s). Defaults to config['electrodeposition_mixing_speed'].
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    # Use provided arguments or fall back to default config
    filling_speed = filling_speed if filling_speed is not None else config['elyte_mix_filling_speed']
    mixing_speed = mixing_speed if mixing_speed is not None else config['elyte_mix_mixing_speed']

    elyte_ports = [port for _, _, port in elyte_info]
    elyte_ratios = [ratio for _, ratio, _ in elyte_info]
    compositions = [ratio / sum(elyte_ratios) for ratio in elyte_ratios]
    elyte_volumes = [comp * volume for comp in compositions]
    
    for vol, port in zip(elyte_volumes,elyte_ports):
        if vol > 0:
            syringe_transfer_and_wash(syringe_pump=syringe_pump, volume=vol, draw_valve_port=port,
                                      dispense_valve_port=compartment, speed=filling_speed, **kwargs)

    syringe_transfer_and_wash(syringe_pump=syringe_pump, volume=volume * 0.5,
                              draw_valve_port=compartment, dispense_valve_port=compartment,
                              speed=mixing_speed, **kwargs)  # Mix the solution slightly
    client.set(name=f'{compartment}_volume', value=volume)


@flow
def electrodeposition(
        data_path: Path,
        experiment_ids: List[str],
        metal_ratios_list: List[List[Tuple[str, float]]],
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
        data_path (str): Folder where the data will be stored.
        experiment_ids (List[str]): Unique identifier for the experiment.
        metal_ratios_list (List[List[Tuple[str, float]]]): A list of lists, where each inner list contains the metal ratios for the
            electrodeposition process corresponding to different flow cells in the setup. Each item in the list
            represents the metal ratios (e.g., [Cu, Co, Ni]) for a specific flow cell.
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
    parallel_cells = config['parallel_cells']

    _valid_precursor_ports = get_valid_precursors()
    
    for cell_str, metal_ratios in zip([str(cell).zfill(2) for cell in range(1,parallel_cells+1)],metal_ratios_list):
        ports_dict = dict(_valid_precursor_ports)
        precursors_info = [(metal, ratio, ports_dict[metal]) for metal, ratio in metal_ratios]
        prepare_elyte_mix(syringe_pump='tecanRX01', elyte_info=precursors_info,
                          compartment=f'WEvial{cell_str}', volume=deposition_volume, **kwargs)
        compartment_fill(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)

    run_pump(pump='longerWE01', speed=pump_speed, **kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, **kwargs)

    asyncio.run(run_method_parallel(parallel_cells=parallel_cells, folder=str(data_path),
                            experiment_ids=experiment_ids, mode="CP", params= {'current':current, 'duration':time_rx}, 
                            tia_gain=0, **kwargs))
    for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
        client.set(name=f'flow_cell{cell_str}_content',value='metal_salts')

    wash_flow_cell(**kwargs)


@flow
def electrosynthesis(
        data_path: Path,
        experiment_ids: List[int],
        elyte_ratios_list: List[List[Tuple[str,float]]],
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
        data_path (str): Folder where the data will be stored.
        experiment_ids (List[int]): Unique identifier for the experiment.
        elyte_ratios_list (List[List[Tuple[str,float]]]): A list of lists, where each inner list represents the composition of catholyte
            used for the reaction in different flow cells. Each item in the list contains the specific concentration
            values (e.g., [H2O, NaCl, etc.] or [CuSO4, H2SO4, etc.]) for a given flow cell's catholyte.
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
    parallel_cells = config['parallel_cells']

    client.set('reaction_status', "0")
    _valid_catholytes_ports = get_valid_electrolytes()

    for cell_str, elyte_ratios, exp_id in zip([str(cell).zfill(2) for cell in range(1, parallel_cells + 1)],
                                            elyte_ratios_list, experiment_ids):
        ports_dict = dict(_valid_catholytes_ports)
        catholyte_info = [(elyte, ratio, ports_dict[elyte]) for elyte, ratio in elyte_ratios]
        
        prepare_elyte_mix(syringe_pump='tecanRX01',elyte_info=catholyte_info,
                          compartment=f'WEvial{cell_str}',volume=catholyte_volume, **kwargs)
        compartment_fill(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)
        client.set(name=f'ID{exp_id}_content', value=json.dumps(dict(elyte_ratios)))

    run_pump(pump='longerWE01', speed=pump_speed, **kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, **kwargs)

    client.set(name='reaction_status', value=time_rx)

    asyncio.run(run_method_parallel(parallel_cells=parallel_cells, folder=str(data_path),
                                    experiment_ids=experiment_ids, mode="CP",
                                    params={'current': current, 'duration': time_rx},
                                    tia_gain=0, **kwargs))

    client.set(name='reaction_status', value="waiting")

    wash_flow_cell(**kwargs)


@flow
def electrodisolution(
        data_path: Path,
        experiment_ids: List[int],
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
        data_path (str): Folder where the data will be stored.
        experiment_ids (List[int]): Unique identifier for the experiment.
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
    parallel_cells = config['parallel_cells']

    for cell_str, exp_id in zip([str(cell).zfill(2) for cell in range(1, parallel_cells + 1)],
                               experiment_ids):
        compartment_fill(source='acid', destination=f'WEvial{cell_str}', volume=catholyte_volume,
                         speed=filling_speed, **kwargs)
        compartment_fill(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)
        client.set(name=f'flow_cell{cell_str}_content', value='acid')

    run_pump(pump='longerCE01', speed=pump_speed, **kwargs)
    run_pump(pump='longerWE01', speed=pump_speed, **kwargs)

    asyncio.run(run_method_parallel(parallel_cells=parallel_cells, folder=str(data_path),
                                    experiment_ids=experiment_ids, mode="CP",
                                    params={'current': 0, 'duration': time_rx},
                                    tia_gain=2, **kwargs))

    wash_flow_cell(**kwargs)

@flow
def execute_experiment(
        metal_ratios_list: List[List[Tuple[str, float]]],
        elyte_ratios_list: List[List[Tuple[str, float]]],
        **kwargs: Any,
)->None:
    """
    Executes the main reaction loop, which includes electrodeposition, reaction, and dissolution
    based on given metal ratios for catalyst composition.
    At the start resets the cache, so that electrolytes and precursors values get updated from default_config.

    Args:
        metal_ratios_list (List[List[Tuple[str, float]]]): A list of lists, where each inner list contains the metal ratios for the
            electrodeposition process corresponding to different flow cells in the setup. Each item in the list
            represents the metal ratios (e.g., [Cu, Co, Ni]) for a specific flow cell.
        elyte_ratios_list (List[List[Tuple[str, float]]]): A list of lists, where each inner list represents the composition of catholyte
            used for the reaction in different flow cells. Each item in the list contains the specific concentration
            values (e.g., [H2O, NaCl, etc.] or [CuSO4, H2SO4, etc.]) for a given flow cell's catholyte.
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    
    parallel_cells = config['parallel_cells']
    measurement_types = ['electrodeposition', 'electrosynthesis', 'electrodissolution', 'uvvis']
    paths = [get_default_folder(step) for step in measurement_types]
    for path, exp_type in zip(paths, measurement_types):
        client.set(f'data_path_{exp_type}', str(path))
    reset_cache()
    experiment_ids = []
    for cell_str, metal_ratio, elyte_ratios in zip([str(cell).zfill(2) for cell in range(1,parallel_cells+1)],
                                            metal_ratios_list, elyte_ratios_list):
        exp_id = add_experiment_to_db(precursor_ratios=metal_ratio, electrolyte_ratios=elyte_ratios, 
                                      metadata={'cell': cell_str})
        client.set(f'ID{exp_id}_catholyte',json.dumps(elyte_ratios))
        client.set(f'ID{exp_id}_metal_ratios', json.dumps(metal_ratio))
        client.set(f'WEvial{cell_str}_EXP_ID', str(exp_id))
        experiment_ids += [exp_id]
    print(experiment_ids)
    electrodeposition(data_path=paths[0], experiment_ids=experiment_ids, metal_ratios_list=metal_ratios_list, **kwargs)
    electrosynthesis(data_path=paths[1], experiment_ids=experiment_ids, elyte_ratios_list=elyte_ratios_list, **kwargs)
    electrodisolution(data_path=paths[2], experiment_ids=experiment_ids, **kwargs)



if __name__ == "__main__":
    pass
    #prepare_elyte_mix(syringe_pump = 'tecanRX01', elyte_ratios = [1,1,1], elyte_ports=['Cu','Co','Ni'], compartment='WEvial01',volume = 10)
    #electrodeposition.serve(
    #        name='trial',
    #        parameters={'data_path':'Data','experiment_id':'test00','metal_ratios':[[1,1,1]],
    #                    'current':-0.004,'time_rx':10,'deposition_volume':10,
    #                    'anolyte_volume':10, 'kwargs':{}},
    #        )
    #electrosynthesis(catholyte_ratios=[[1,0,0,0,0,0,0,0,0]],current=+0.004,catholyte_volume=10, anolyte_volume=10)
    #electrodisolution(time_rx=10,catholyte_volume=10, anolyte_volume=10)
    #run_cp('potentiostat01',-0.004,5)


