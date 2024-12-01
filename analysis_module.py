import os
import json
import pickle
from pathlib import Path
import time
from typing import Optional, Any
from datetime import datetime, timedelta

from prefect import task, flow, get_run_logger

from default_config import DEFAULT_CONFIG
from decorators import with_lock
from redis_client import client
from tecan_pumps import draw_and_dispense_and_wash_tecan, draw_and_dispense_tecan_unlocked, wash_compartment

user_name = os.getenv("USER") or os.getenv("USERNAME")
_uv_vis_path =  Path(
    rf"C:\Users\{user_name}\Aspuru-Guzik Lab Dropbox\Lab Manager Aspuru-Guzik\PythonScript\HPLCMS_characterization\sample_to_measure"
)

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
    parallel_cells = config['parallel_cells']

    logger = get_run_logger()

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
                    for cell in range(parallel_cells):
                        cell_str = str(cell).zfill(2)
                        WEvial = f'WEvial{cell_str}'
                        empty_vials = [json.loads(item) for item in client.lrange('empty_vials', 0, -1)]

                        if empty_vials:
                            vial = empty_vials.pop(0)
                            client.delete('empty_vials')

                            for item in empty_vials:
                                client.rpush('empty_vials', json.dumps(item))

                            draw_and_dispense_and_wash_tecan(
                                'tecanAz01', volume=volume, draw_valve_port=WEvial,
                                dispense_valve_port=vial, speed=config['aliquot_filling_speed'], **kwargs
                            )
                            aliquot_time = time.time()
                            fill_vial_detection_mix(vial, aliquot_filling_speed=config['aliquot_filling_speed']
                                                    , **kwargs)
                            aliquot_time = (aliquot_time + time.time()) / 2
                            catholyte = client.get(f'flowcell{cell_str}_reaction_catholyte')
                            metal_ratios = client.get(f'flowcell{cell_str}_reaction_metal_ratios')
                            measure_time = datetime.utcnow() + timedelta(minutes=30)
                            time_rxn = aliquot_time - initial_time
                            measure_vial.submit(task_name=f'Measurment of {vial} from {WEvial}',
                                                run_at=measure_time
                                                )(vial=vial,time_rxn=time_rxn,catholyte=catholyte,
                                                  metal_ratios=metal_ratios, **kwargs)
                            #client.rpush('filled_vials', json.dumps(vial_info))

                            aliquotes_sent += 1
                            period_timing += aliquote_interval
                        else:
                            logger.warning('Warning! There are no empty vials, waiting for one to get free')
                            time.sleep(5)
                time.sleep(2.5)


@task
def generate_pickle_file(
        compositions_str: str,
        elyte: str,
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
def measure_vial(
        vial: str,
        time_rxn: float,
        catholyte: str,
        metal_ratios: str,
        **kwargs
)->None:

    config = {**DEFAULT_CONFIG,**kwargs}
    wash_vial_repeats = config['wash_vial_repeats']
    wash_vial_volume = config['wash_vial_volume']
    wash_vial_speed = config['wash_vial_speed']
    wash_vial_last_empty = config['wash_vial_last_empty']
    filling_speed = config['aliquot_filling_speed']

    logger = get_run_logger()

    draw_and_dispense_and_wash_tecan(
        'tecanAZ01', 0.5, draw_valve_port=vial, dispense_valve_port='uv-vis',
        speed=filling_speed, **kwargs
    )
    generate_pickle_file(
        elyte=catholyte,
        compositions_str=metal_ratios,
        time_rxn=round(float(time_rxn))
    )
    logger.info(f'Sample {vial} sent to UV-VIS')

    wash_compartment(syringe_pump='tecanAZ01', compartment=vial, repeats=wash_vial_repeats,
                     wash_vol=wash_vial_volume,speed=wash_vial_speed, speed_last_empty=wash_vial_last_empty,
                     **kwargs)

    # Add vial back to empty vials list
    client.rpush('empty_vials', json.dumps(vial))


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
    aliquot_filling_speed = aliquot_filling_speed if aliquot_filling_speed is not None else config[
        'aliquot_filling_speed']

    draw_and_dispense_tecan_unlocked(
        'tecanAZ01', volume=0.2 - aliquot_volume, draw_valve_port='water',
        dispense_valve_port=vial, speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d1_volume, 'd1', vial,
                                     speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d2_volume, 'd2', vial,
                                     speed=aliquot_filling_speed, **kwargs)
    draw_and_dispense_and_wash_tecan('tecanAZ01', d3_volume, 'd3', vial,
                                     speed=aliquot_filling_speed, **kwargs)