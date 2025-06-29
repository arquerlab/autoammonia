import json
import socket
from pathlib import Path
import time
from typing import Optional, Any
from datetime import datetime, timedelta
from prefect import flow, get_run_logger
import pandas as pd

from .config.config import DEFAULT_CONFIG
from .db.db_functions import add_results_to_db
from .hardware.uv_vis_module import acquire_spectrum
from .utils.decorators import with_lock
from .utils.prefect import trigger_deployment
from .utils.redis_client import client
from .hardware.syringe_pumps import syringe_transfer_and_wash, syringe_transfer_unlocked, compartment_wash, compartment_fill
from .utils.files import get_default_folder, transfer_file_scp


#main_hostname = client.get('main_hostname')


@flow
def track_reaction(
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
    
    num_aliquots = num_aliquots if num_aliquots is not None else config['aliquot_number']
    volume = volume if volume is not None else config['aliquot_volume']
    
    logger = get_run_logger()

    while True:
        reaction_status = client.get('reaction_status')
        if reaction_status == "waiting":
            time.sleep(20)
        elif reaction_status == "0":
            time.sleep(0.1)
        else:
            logger.info('Reaction started, aliquotes tracking initiated')
            initial_time = time.time()
            aliquotes_sent = 0
            aliquote_interval = (float(reaction_status) - 60) / num_aliquots
            period_timing = time.time() + aliquote_interval - 30

            while aliquotes_sent < num_aliquots:
                current_time = time.time()

                if period_timing <= current_time:
                    take_aliquots(initial_reaction_time=initial_time, volume=volume)
                    aliquotes_sent += 1
                    logger.info(f'Aliquot {aliquotes_sent} taken at {current_time - initial_time:.2f} seconds')
                    period_timing += aliquote_interval
                    
                time.sleep(2.5)
            # Wait unitl reaction is finished
            while True:
                reaction_status = client.get('reaction_status')
                if reaction_status == "waiting":
                    logger.info('Reaction finished, all aliquots taken')
                    break
                else:
                    time.sleep(5)

@flow
def take_aliquots(
        initial_reaction_time: float,
        volume: float,
        **kwargs,
)->None:
    config = {**DEFAULT_CONFIG, **kwargs}
    
    parallel_cells = config['parallel_cells']
    dark_time = config['detection_dark_time']
    
    logger = get_run_logger()
    
    for cell_str in [str(cell).zfill(2) for cell in range(1, parallel_cells+1)]:
        WEvial = f'WEvial{cell_str}'
        exp_id = client.get(f'WEvial{cell_str}_EXP_ID')
        while True:
            vial = client.lpop('empty_vials')
            if vial:
                break
            else:
                logger.warning('Warning! There are no empty vials, waiting for one to get free')
                time.sleep(5)
        syringe_transfer_and_wash(
            'tecanAZ01', volume=volume, draw_valve_port=WEvial,
            dispense_valve_port=vial, speed=config['aliquot_filling_speed'], **kwargs
        )
        logger.info(f'Aliquot of {volume} mL taken from {WEvial} to {vial}')
        aliquot_time = time.time()
        fill_vial_detection_mix(vial, aliquot_filling_speed=config['aliquot_filling_speed']
                                , **kwargs)
        aliquot_time = (aliquot_time + time.time()) / 2
        measure_time = datetime.now() + timedelta(seconds=dark_time)
        time_rxn = aliquot_time - initial_reaction_time
        trigger_deployment(deployment='measure-vial/measure_vial_uv_vis_flow',
                                     scheduled_time=measure_time,
                                     parameters={'vial': vial, 'time_rxn': time_rxn, 'exp_id': exp_id, 'kwargs': kwargs})
        logger.info(f'Programmed measurement of {vial} from {WEvial} at {measure_time}')
        

@flow
def measure_vial(
        vial: str,
        time_rxn: float,
        exp_id: str,
        **kwargs: Any,
)->None:

    config = {**DEFAULT_CONFIG,**kwargs}
    wash_vial_repeats = config['wash_vial_repeats']
    wash_vial_volume = config['wash_vial_volume']
    wash_vial_speed = config['wash_vial_speed']
    wash_vial_last_empty = config['wash_vial_last_empty']
    filling_speed = config['aliquot_filling_speed']
    uv_vis_integration_time = config['uv_vis_integration_time']
    uv_vis_wash_volume = config['uv_vis_wash_volume']

    logger = get_run_logger()

    compartment_fill(
        syringe_pump='tecanAZ01', source=vial, destination='uv_vis',volume=0.5,
        speed=filling_speed, **kwargs
    )
    logger.info(f'Sample {vial} sent to UV-VIS for measurement')
    df = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time)
    logger.info(f'Sample {vial} measured at UV-VIS')
    folder = get_default_folder('UVVIS')
    filepath = folder / f'ID{exp_id}_RXT{time_rxn}_VIAL{vial}.csv'
    df.to_csv(filepath, index=False)
    hostname = socket.gethostname()
    if hostname != client.get('main_hostname'):
        filepath_db = transfer_file_scp(local_file=filepath, remote_folder=client.get('data_path_uvvis'),
                          remote_user='poten', remote_host=client.get('main_hostname'), remote_password="potato12")
    else:
        filepath_db = filepath
    
    add_results_to_db(
        experiment_id=exp_id, result_type='UVVIS', result_role='raw_data', file_path=str(filepath_db),
        metadata={'original_path': filepath if hostname != client.get('main_hostname') else str(filepath_db),
                  'vial': vial, 'time_rxn': time_rxn, 'integration_time': uv_vis_integration_time}
    )
    
    # UV-VIS washing of flow cell
    compartment_fill(
        syringe_pump='tecanAZ01', volume=uv_vis_wash_volume, draw_valve_port=vial, dispense_valve_port='uv_vis',
        speed=filling_speed, **kwargs
    )
    logger.info(f'UV-VIS flow cell washed with {uv_vis_wash_volume} mL of water')

    compartment_wash(syringe_pump='tecanAZ01', compartment=vial, repeats=wash_vial_repeats,
                     wash_vol=wash_vial_volume, speed=wash_vial_speed, speed_last_empty=wash_vial_last_empty,
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
    logger = get_run_logger()
    # Use provided arguments or fall back to default config
    aliquot_volume = aliquot_volume if aliquot_volume is not None else config['aliquot_volume']
    d1_volume = d1_volume if d1_volume is not None else config['detection_reagent_1_volume']
    d2_volume = d2_volume if d2_volume is not None else config['detection_reagent_2_volume']
    d3_volume = d3_volume if d3_volume is not None else config['detection_reagent_3_volume']
    aliquot_filling_speed = aliquot_filling_speed if aliquot_filling_speed is not None else config[
        'aliquot_filling_speed']

    syringe_transfer_unlocked(
        'tecanAZ01', volume=0.2 - aliquot_volume, draw_valve_port='water',
        dispense_valve_port=vial, speed=aliquot_filling_speed, **kwargs)
    syringe_transfer_and_wash('tecanAZ01', d1_volume, 'd1', vial,
                              speed=aliquot_filling_speed, **kwargs)
    syringe_transfer_and_wash('tecanAZ01', d2_volume, 'd2', vial,
                              speed=aliquot_filling_speed, **kwargs)
    syringe_transfer_and_wash('tecanAZ01', d3_volume, 'd3', vial,
                              speed=aliquot_filling_speed, **kwargs)
    logger.info(f'Detection mix filled in vial {vial} with volumes: '
                f'aliquot={aliquot_volume}, d1={d1_volume}, d2={d2_volume}, d3={d3_volume}')

def analysis_module_deploy():
    track_reaction.from_source(
        source=Path(__file__).parent,
        entrypoint="analysis_module.py:track_reaction",
    ).deploy(
        name="analysis_module_flow",
        work_pool_name="analysis_module_pool",
    )
    track_reaction.from_source(
        source=Path(__file__).parent,
        entrypoint="analysis_module.py:measure_vial",
    ).deploy(
        name="measure_vial_uv_vis_flow",
        work_pool_name="analysis_module_pool",
    )