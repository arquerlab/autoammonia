import os
import time
from datetime import datetime
from typing import Any
from prefect import get_run_logger, flow

from .analysis_module import fill_vial_detection_mix
from .hardware.syringe_pumps import syringe_transfer_unlocked, syringe_transfer_uvvis_and_wash
from .config.config import DEFAULT_CONFIG

@flow
def calibration(
    calibration_dark_time: int | None = None,
    calibration_path: str | None = None,
    calibration_file: str | None = None,
    calibration_concentrations: list[float] | None = None,
    **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    calibration_dark_time = calibration_dark_time if calibration_dark_time is not None else config['calibration_dark_time']
    calibration_path = calibration_path if calibration_path is not None else config['calibration_path']
    default_calibration_file = os.path.join(calibration_path, datetime.now().strftime('%y%m%d_%H%M'))
    calibration_file = calibration_file if calibration_file is not None else default_calibration_file
    concentrations = [0.5, 0.25, 0.1, 0.05, 0.025, 0.01, 0.005, 0.0025, 0.001]
    calibration_concentrations = calibration_concentrations if calibration_concentrations is not None else concentrations
    logger = get_run_logger()

    
    aliquot_volumes = []
    for i, concentration in enumerate(calibration_concentrations[-3::-3]):
        inp = input(f"Place a {concentration}mg/L N solution in WEvial01 and press Enter to continue")
        for j, ratio in enumerate([1,2,4]):
            vial = f'vial{i*3+j+1}'
            aliquot_volume = 0.2 / ratio
            aliquot_volumes.append(aliquot_volume)
            syringe_transfer_unlocked(syringe_pump='tecanAZ01', volume=aliquot_volume, draw_valve_port='water',
                                      dispense_valve_port=vial, speed=0.1)
            logger.info(f"Transferred {aliquot_volume} mL of {concentration}mg/L N solution to {vial}")
    
    start_time = time.time()
    for i, aliquot_volume in enumerate(aliquot_volumes):
        vial = f'vial{i+1}'
        fill_vial_detection_mix(syringe_pump='tecanAZ01', vial=vial, aliquot_volume=aliquot_volume, d1_volume=0.2, d2_volume=0.1, d3_volume=0.1, aliquot_filling_speed=0.1)
        logger.info(f"Filled {vial} with {aliquot_volume} mL of {concentration}mg/L N solution")
    sleep_time = config['detection_dark_time'] - (time.time() - start_time)
    if sleep_time > 0:
        logger.info(f"Waiting for {sleep_time} seconds to reach detection dark time")
        time.sleep(sleep_time)
    logger.info(f"Detection dark time reached")

    for i, aliquot_volume in enumerate(aliquot_volumes):
        vial = f'vial{i+1}'
        syringe_transfer_uvvis_and_wash(syringe_pump='tecanAZ01', aliquot_volume=0.3, 
                                draw_valve_port=vial, speed=config['aliquot_filling_speed'],
                                wash_repeats=config['syringe_wash_repeats'],
                                wash_vol=config['syringe_wash_volume'],
                                wash_speed=config['syringe_wash_speed'], **kwargs)
        logger.info(f"Transferred {0.3} mL of vial {vial} to UV-VIS and washed valves")

def main():
    calibration(calibration_dark_time = 1)
if __name__ == "__main__":
    main()