import os.path
import time
from datetime import datetime
import json
from typing import Optional, List, Any
from prefect import flow

from default_config import DEFAULT_CONFIG, CONNECTIONS_INFO, CONFIG_COMPONENTS

from redis_client import client
from utils import reset_cache, get_valid_precursors, get_valid_electrolytes
from valco_valve import switch_port_valve
from potentiostat import run_cp
from longer_pumps import run_pump, stop_pump
from tecan_pumps import draw_and_dispense_tecan, fill_compartment, wash_syringe_unlocked, wash_compartment, draw_and_dispense_and_wash_tecan

from decorators import with_lock





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
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port=port_name, 
                                    dispense_valve_port="waste", speed=speed, **kwargs)

    # Filling of al stock solution tubes leading to the valve assigned to the pump
    wash_valve = False
    for port_name, port_info in CONNECTIONS_INFO[syringe_valve].items():
        if port_info['usage'].lower() == 'stock':
            input_tube_volume = port_info['volume']
            switch_port_valve(valve=syringe_valve, port=port_name, **kwargs)
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=input_tube_volume, draw_valve_port="valve", 
                                    dispense_valve_port="waste", speed=speed, **kwargs)
            wash_valve = True

    wash_syringe_unlocked(syringe_pump, repeats=config['syringe_wash_repeats'],wash_vol=wash_vol,
                          speed=config['syringe_wash_speed'],wash_valve=wash_valve, **kwargs)

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
    air_flush_factor = config["air_flush_speed"]

    # Select valve according to the pump type
    if 'RX' in syringe_pump.upper():
        syringe_valve = 'valveRX' + syringe_pump[-2:]
    else:
        syringe_valve = 'valveAZ' + syringe_pump[-2:]

    # Empty of all the stock solution tubes leading to the pump valve directly
    air_flush_volume = air_flush_factor * CONFIG_COMPONENTS[syringe_pump]['syringe_volume'] * 1000
    for port_name, port_info in CONNECTIONS_INFO[syringe_pump].items():
        if port_info['usage'].lower() == 'stock':
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port='air', 
                                    dispense_valve_port=port_name, speed=air_flush_speed, **kwargs)

    # Emptying of al stock solution tubes leading to the valve assigned to the pump
    for port_name, port_info in CONNECTIONS_INFO[syringe_valve].items():
        if port_info['usage'].lower() == 'stock':
            switch_port_valve(valve=syringe_valve, port=port_name, **kwargs)
            draw_and_dispense_tecan(syringe_pump=syringe_pump, volume=air_flush_volume, draw_valve_port="air", 
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
    
    run_pump(pump='longerWE01', speed=pump_speed, direction=False, **kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, direction=False, *kwargs)
    time.sleep(wash_time)
    client.set(name='flow_cell_content',value='empty_contaminated')
    stop_pump(pump='longerWE01', *kwargs)
    stop_pump(pump='longerCE01', *kwargs)


@flow
def wash_flow_cell(
        repeats: Optional[int] = None,
        wash_time: Optional[float] = None,
        pump_speed: Optional[float] = None,
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
        pump_speed (Optional[float]): Pump speed during flushing (rpm). Defaults to config['wash_flow_cell_speed'].
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
    pump_speed = pump_speed if pump_speed is not None else config['wash_flow_cell_speed']
    filling_speed = filling_speed if filling_speed is not None else config['wash_flow_cell_filling_speed']
    wash_comp_repeats = wash_comp_repeats if wash_comp_repeats is not None else config['wash_flow_cell_wash_comp_repeats']
    wash_comp_volume = wash_comp_volume if wash_comp_volume is not None else config['wash_flow_cell_wash_comp_volume']
    wash_comp_speed = wash_comp_speed if wash_comp_speed is not None else config['wash_flow_cell_wash_comp_speed']
    wash_comp_speed_last_empty = wash_comp_speed_last_empty if wash_comp_speed_last_empty is not None else config['wash_flow_cell_wash_comp_speed_last_empty']

    empty_and_stop_pumps(wash_time=wash_time, pump_speed=pump_speed, **kwargs)

    for _ in range(repeats):
        fill_compartment(source='water', destination='WEvial01', volume=wash_volume, speed=filling_speed, **kwargs)
        fill_compartment(source='water', destination='CEvial01', volume=wash_volume, speed=filling_speed, **kwargs)
        run_pump(pump='longerWE01', speed=pump_speed, **kwargs)
        run_pump(pump='longerCE01', speed=pump_speed, **kwargs)
        client.set(name='flow_cell_content',value='water_contaminated')
        time.sleep(wash_time)

        wash_compartment(syringe_pump='tecanRX01', compartment='WEvial01', repeats=wash_comp_repeats, 
                         wash_vol=wash_comp_volume, pump_speed=wash_comp_speed, 
                         pump_speed_last_empty=wash_comp_speed_last_empty, **kwargs)
        wash_compartment(syringe_pump='tecanRX01', compartment='CEvial01', repeats=wash_comp_repeats, 
                         wash_vol=wash_comp_volume, pump_speed=wash_comp_speed, 
                         pump_speed_last_empty=wash_comp_speed_last_empty,**kwargs)

        empty_and_stop_pumps(wash_time=wash_time, pump_speed=pump_speed,**kwargs)

    client.set(name='flow_cell_content',value='clean')
    client.set(name='WE_vial01_volume', value=0)
    client.set(name='CE_vial01_volume', value=0)

@flow
def prepare_elyte_mix(
        syringe_pump: str,
        elyte_ratios: List[float],
        elyte_ports: List[str],
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
        elyte_ratios (List[float]): List of metal ratios.
        elyte_ports (List[str]): List of valve ports corresponding to the electrolyte components to be used.
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

    compositions = [ratio / sum(elyte_ratios) for ratio in elyte_ratios]
    volumes = [comp * volume for comp in compositions]
    
    for vol, metal in zip(volumes,elyte_ports):
        if vol > 0:
            draw_and_dispense_and_wash_tecan(syringe_pump=syringe_pump, volume=vol, draw_valve_port=metal,
                                             dispense_valve_port=compartment, speed=filling_speed, **kwargs)

    draw_and_dispense_and_wash_tecan(syringe_pump=syringe_pump, volume=volume * 0.5,
                                     draw_valve_port=compartment, dispense_valve_port=compartment,
                                     speed=mixing_speed, **kwargs)  # Mix the solution slightly
    client.set(name=f'{compartment}_volume', value=volume)


@flow
def electrodeposition(
        data_path: str,
        experiment_id: str,
        metal_ratios: List[List[float]],
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
        metal_ratios (List[List[float]]): A list of lists, where each inner list contains the metal ratios for the
            electrodeposition process corresponding to different flow cells in the setup. Each item in the list
            represents the metal ratios (e.g., [Cu, Co, Ni]) for a specific flow cell.
        current (Optional[float]): Current applied (A). Defaults to config['electrodeposition_current'].
        time_rx (Optional[float]): Duration for current application (s). Defaults to config['electrodeposition_time'].
        deposition_volume (Optional[float]): Solution volume (mL) prepared and used. Defaults to config['electrodeposition_deposition_volume'].
        anolyte_volume (Optional[float]): Volume of anolyte solution (mL). Defaults to config['electrodeposition_anolyte_volume'].
        pump_speed (Optional[float]): Pump speed during electrodeposition (rpm). Defaults to config['electrodeposition_pump_speed'].
        filling_speed (Optional[float]): Speed for filling compartments (mL/s). Defaults to config['electrodeposition_filling_speed'].
        data_path (Optional[str]): Path where data is meant to be stored. Default to config['electrodeposition_data_path']
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}

    current = current if current is not None else config['electrodeposition_current']
    time_rx = time_rx if time_rx is not None else config['electrodeposition_time']
    deposition_volume = deposition_volume if deposition_volume is not None else config['electrodeposition_deposition_volume']
    anolyte_volume = anolyte_volume if anolyte_volume is not None else config['electrodeposition_anolyte_volume']
    pump_speed = pump_speed if pump_speed is not None else config['electrodeposition_pump_speed']
    filling_speed = filling_speed if filling_speed is not None else config['electrodeposition_filling_speed']
    data_path = data_path if data_path is not None else config['electrodeposition_data_path']
    parallel_cells = config['parallel_cells']

    precursors, precursors_ports = get_valid_precursors()
    
    for cell_str, ratios_set in zip([str(cell).zfill(2) for cell in range(1,parallel_cells+1)],metal_ratios):
        prepare_elyte_mix(syringe_pump='tecanRX01', elyte_ratios=ratios_set, elyte_ports=precursors_ports,
                          compartment=f'WEvial{cell_str}', volume=deposition_volume, **kwargs)
        fill_compartment(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)

    run_pump(pump='longerWE01', speed=pump_speed, **kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, **kwargs)

    potentiostats = ["potentiostat"+str(cell).zfill(2) for cell in range(1,parallel_cells+1)]
    filenames = [data_path+'/'+experiment_id+f'_cell{str(cell).zfill(2)}.csv' for cell in range(1,parallel_cells+1)]
    run_cp.map(potentiostat=potentiostats, current=[current] * parallel_cells,
               time_rx=[time_rx] * parallel_cells, tia_gain=0,filpath=filenames, **kwargs)
    client.set(name='flow_cell_content',value='metal_salts')

    wash_flow_cell(**kwargs)


@flow
def electrosynthesis(
        data_path: str,
        experiment_id: str,
        catholyte_ratios: List[List[float]],
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
        catholyte_ratios (List[List[float]]): A list of lists, where each inner list represents the composition of catholyte
            used for the reaction in different flow cells. Each item in the list contains the specific concentration
            values (e.g., [H2O, NaCl, etc.] or [CuSO4, H2SO4, etc.]) for a given flow cell's catholyte.
        current (Optional[float]): Applied current (A). Defaults to config['reaction_current'].
        time_rx (Optional[float]): Duration of the reaction (s). Defaults to config['reaction_time'].
        catholyte_volume (Optional[float]): Volume of catholyte (mL). Defaults to config['reaction_catholyte_volume'].
        anolyte_volume (Optional[float]): Volume of anolyte (mL). Defaults to config['reaction_anolyte_volume'].
        pump_speed (Optional[float]): Pump speed during reaction (rpm). Defaults to config['reaction_pump_speed'].
        filling_speed (Optional[float]): Speed for filling compartments (mL/s). Defaults to config['reaction_filling_speed'].
        data_path (Optional[str]): Path where data is meant to be stored. Default to config['reaction_data_path']
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
    catholytes, catholytes_ports = get_valid_electrolytes()

    for cell_str, ratios_set in zip([str(cell).zfill(2) for cell in range(1,parallel_cells+1)],catholyte_ratios):
        prepare_elyte_mix(syringe_pump='tecanRX01',elyte_ratios=ratios_set,elyte_ports=catholytes_ports,
                          compartment=f'WEvial{cell_str}',volume=catholyte_volume, **kwargs)
        fill_compartment(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)
        client.set(name='flow_cell_content', value=ratios_set)

    run_pump(pump='longerWE01', speed=pump_speed, *kwargs)
    run_pump(pump='longerCE01', speed=pump_speed, *kwargs)

    client.set(name='reaction_status', value=time_rx)

    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [data_path+'/'+experiment_id+f'_cell{str(cell).zfill(2)}.csv' for cell in range(1,parallel_cells+1)]
    run_cp.map(potentiostat=potentiostats, current=[current] * parallel_cells,
               time_rx=[time_rx] * parallel_cells, tia_gain=0, filpath=filenames, **kwargs)
    client.set(name='reaction_status', value="waiting")

    wash_flow_cell(**kwargs)


@flow
def electrodisolution(
        data_path: str,
        experiment_id: str,
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
        data_path (Optional[str]): Path where data is meant to be stored. Default to config['electrodisolution_data_path']
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

    for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]:
        fill_compartment(source='acid', destination=f'WEvial{cell_str}', volume=catholyte_volume,
                         speed=filling_speed, **kwargs)
        fill_compartment(source='anolyte', destination=f'CEvial{cell_str}', volume=anolyte_volume,
                         speed=filling_speed, **kwargs)

    run_pump(pump='longerCE01', speed=pump_speed, **kwargs)
    run_pump(pump='longerWE01', speed=pump_speed, **kwargs)

    client.set(name='flow_cell_content',value='acid')

    potentiostats = ["potentiostat" + str(cell).zfill(2) for cell in range(1, parallel_cells + 1)]
    filenames = [data_path + '/' + experiment_id + f'_cell{str(cell).zfill(2)}.csv' for cell in
                 range(1, parallel_cells + 1)]
    run_cp.map(potentiostat=potentiostats, current=[0] * parallel_cells,
               time_rx=[time_rx] * parallel_cells, tia_gain=1, filpath=filenames, **kwargs)

    wash_flow_cell(**kwargs)

@flow
def execute_reaction(
        metal_ratios: List[List[float]],
        electrolytes: List[List[float]],
        **kwargs: Any,
)->None:
    """
    Executes the main reaction loop, which includes electrodeposition, reaction, and dissolution
    based on given metal ratios for catalyst composition.
    At the start resets the cache, so that electrolytes and precursors values get updated from default_config.

    Args:
        metal_ratios (LList[List[float]]): A list of lists, where each inner list contains the metal ratios for the
            electrodeposition process corresponding to different flow cells in the setup. Each item in the list
            represents the metal ratios (e.g., [Cu, Co, Ni]) for a specific flow cell.
        electrolytes (List[List[float]]): A list of lists, where each inner list represents the composition of catholyte
            used for the reaction in different flow cells. Each item in the list contains the specific concentration
            values (e.g., [H2O, NaCl, etc.] or [CuSO4, H2SO4, etc.]) for a given flow cell's catholyte.
        **kwargs (Any): Additional keyword arguments to override the default configuration.
    """
    config = {**DEFAULT_CONFIG, **kwargs}
    
    parallel_cells = config['parallel_cells']
    paths = [config['electrodeposition_data_path'],config['reaction_data_path'],config['electrodisolution_data_path']]
    experiment_id = datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss')

    reset_cache()

    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
        
    
    for cell_str, metal_ratio, elyte in zip([str(cell).zfill(2) for cell in range(1,parallel_cells+1)],metal_ratios, electrolytes):
        client.set(f'flow_cell_{cell_str}_catholyte',json.dumps(elyte))
        client.set(f'flow_cell_{cell_str}_metal_ratios', json.dumps(metal_ratio))

    electrodeposition(data_path=paths[0], experiment_id=experiment_id, metal_ratios=metal_ratios, **kwargs)
    electrosynthesis(data_path=paths[1], experiment_id=experiment_id, catholyte_ratios=electrolytes, **kwargs)
    electrodisolution(data_path=paths[2], experiment_id=experiment_id, **kwargs)



if __name__ == "__main__":
    pass
    #prepare_elyte_mix(syringe_pump = 'tecanRX01', elyte_ratios = [1,1,1], elyte_ports=['Cu','Co','Ni'], compartment='WEvial01',volume = 10)
    electrodeposition.serve(
            name='trial',
            parameters={'data_path':'Data','experiment_id':'test00','metal_ratios':[[1,1,1]],
                        'current':-0.004,'time_rx':10,'deposition_volume':10,
                        'anolyte_volume':10, 'kwargs':{}},
            )
    #electrosynthesis(catholyte_ratios=[[1,0,0,0,0,0,0,0,0]],current=+0.004,catholyte_volume=10, anolyte_volume=10)
    #electrodisolution(time_rx=10,catholyte_volume=10, anolyte_volume=10)
    #run_cp('potentiostat01',-0.004,5)


