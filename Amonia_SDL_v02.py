import os
import json
import pickle
from pathlib import Path
import traceback
import time
from typing import Optional, List, Any
from prefect import task, flow

from default_config import DEFAULT_CONFIG, CONNECTIONS_INFO, CONFIG_COMPONENTS

from redis_client import client
from valco_valve import switch_port_valve
from potentiostat import run_cp
from longer_pumps import run_pump, stop_pump, check_pump
from tecan_pumps import draw_and_dispense_tecan, fill_compartment, wash_syringe_unlocked, wash_compartment, draw_and_dispense_and_wash_tecan, draw_and_dispense_tecan_unlocked

from decorators import with_lock



user_name = os.getenv("USER") or os.getenv("USERNAME")
_uv_vis_path =  Path(
    rf"C:\Users\{user_name}\Aspuru-Guzik Lab Dropbox\Lab Manager Aspuru-Guzik\PythonScript\HPLCMS_characterization\sample_to_measure"
)
   
    








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
    
    pass
    #run_cp('potentiostat01',-0.004,5)


