import os
import time
from datetime import datetime
from typing import Any
from prefect import get_run_logger, flow
import numpy as np
import pandas as pd

from .analysis_module import fill_vial_detection_mix
from .hardware.syringe_pumps import syringe_transfer_unlocked, syringe_transfer_uvvis_and_wash, compartment_wash_uvvis
from .config.config import DEFAULT_CONFIG
from .hardware.uv_vis_module import acquire_spectrum

@flow
def calibration(
    calibration_path: str | None = None,
    calibration_file: str | None = None,
    calibration_concentrations: list[float] | None = None,
    **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    calibration_path = calibration_path if calibration_path is not None else config['calibration_path']
    if not os.path.exists(calibration_path):
        os.makedirs(calibration_path)
    default_calibration_file = os.path.join(calibration_path, datetime.now().strftime('%y%m%d_%H%M'))
    calibration_file = calibration_file if calibration_file is not None else default_calibration_file
    concentrations = [0.5, 0.25, 0.1, 0.05, 0.025, 0.01, 0.005, 0.0025, 0.001]
    calibration_concentrations = calibration_concentrations if calibration_concentrations is not None else concentrations

    wash_uvvis_repeats = config['uv_vis_wash_repeats']
    wash_uvvis_volume = config['uv_vis_wash_volume']
    wash_uvvis_speed = config['uv_vis_wash_speed']
    uv_vis_aliquot_volume = config['uv_vis_aliquot_volume']
    uv_vis_integration_time = config['uv_vis_integration_time']
    filling_speed = config['aliquot_filling_speed']
    wash_vial_repeats = config['wash_vial_repeats']
    wash_vial_volume = config['wash_vial_volume']
    wash_vial_speed = config['wash_vial_speed']
    
    
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
        syringe_transfer_uvvis_and_wash(
            syringe_pump='tecanAZ01', aliquot_volume=uv_vis_aliquot_volume, draw_valve_port='water', speed=filling_speed,
            wash_repeats=0, wash_vol=0, wash_speed=wash_vial_speed, **kwargs
        )
        logger.info(f'[calibration] UV-VIS flow cell filled with water (reference)')
        df_ref_dark = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=True)
        logger.info(f'[calibration] Dark reference spectrum acquired')
        df_ref = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=False)
        logger.info(f'[calibration] Reference spectrum acquired')
        syringe_transfer_uvvis_and_wash(
            syringe_pump='tecanAZ01', aliquot_volume=uv_vis_aliquot_volume, draw_valve_port=vial, speed=filling_speed,
            wash_repeats=wash_vial_repeats, wash_vol=wash_vial_volume, wash_speed=wash_vial_speed, **kwargs
        )
        logger.info(f'[calibration] Sample {vial} sent to UV-VIS for measurement')
        df_sample_dark = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=True)
        logger.info(f'[calibration] Sample {vial} dark spectrum acquired')
        df_sample = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=False)
        logger.info(f'[calibration] Sample {vial} spectrum acquired')
        compartment_wash_uvvis(syringe_pump='tecanAZ01', 
                    repeats=wash_uvvis_repeats, wash_vol=wash_uvvis_volume, speed=wash_uvvis_speed, **kwargs)
        logger.info(f'[calibration] UV-VIS flow cell washed with water')
        df = pd.DataFrame({
            "Wavelength (nm)": df_ref["Wavelength (nm)"],
            "Reference_dark": df_ref_dark["Intensity"],
            "Reference": df_ref["Intensity"],
            "Sample_dark": df_sample_dark["Intensity"],
            "Sample": df_sample["Intensity"],
        })
        df["Reference_dark_corrected"] = df["Reference"] - df["Reference_dark"]
        df["Sample_dark_corrected"] = df["Sample"] - df["Sample_dark"]
        df["Transmittance"] = df["Sample_dark_corrected"] / df["Reference_dark_corrected"]
        df["Absorption"] = -np.log10(df["Transmittance"])
        df.to_csv(os.path.join(calibration_path, f'calibration_{i+1}.csv'), index=False)
def main():
    calibration()
if __name__ == "__main__":
    main()