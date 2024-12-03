from matterlab_pumps import TecanXCPump
from matterlab_valves import ValcoSelectionValve
from potentiostat_minimalmodbus import PotentiometerCommand
from peristaltic_pump import Longer_BT100_3J_Pump

CONFIG_COMPONENTS = {'longerWE01': {'class': Longer_BT100_3J_Pump, 'com_port': '/dev/longer_pumps', 'address': '1'},
                     'longerCE01': {'class': Longer_BT100_3J_Pump, 'com_port': '/dev/longer_pumps', 'address': '2'},
                     'tecanRX01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 2, 'syringe_volume': 2.5e-3,
                         'num_valve_port': 13,
                                   'ports': None},
                     'valveRX01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveRX01', 'num_port':10,
                                   'ports': None},
                     'tecanAZ01': {'class': TecanXCPump, 'com_port': '/dev/tecan_pumps', 'address': 1, 'syringe_volume': 1e-3,
                                   'num_valve_port': 13,
                                   'ports': None},
                     'valveAZ01': {'class': ValcoSelectionValve, 'com_port': '/dev/valveAZ01','num_port':10,
                                   'ports': None},
                     'potentiostat01': {'port': '/dev/potentiostat01', 'slaveaddress': 1}
                     }

DEFAULT_CONFIG = {
    "parallel_cells":1,
    "delete_previous_queue": True,
    "emergency_stop_retries": 10,
    "emergency_stop_retries_delay":5,
    "potentiostat_acq_timeout": 30,
    
    "longer_acq_timeout":20,
    "longer_func_timeout":15,
    "longer_retries":3,
    "longer_retries_emergency_stop":10,
    "longer_retries_delay_emergency_stop":5,
    
    "valve_retries":3,
    
    "draw_and_dispense_retries": 3,
    "function_timeout": 600,
    "acquisition_timeout": 300,
    
    "syringe_fail_retrials": 5,

    "elyte_mix_filling_speed": 0.2,
    "elyte_mix_mixing_speed": 0.4,
    
    "electrodeposition_current": 2.82743339,
    "electrodeposition_time": 6 * 60,
    "electrodeposition_deposition_volume": 10,
    "electrodeposition_anolyte_volume": 10,
    "electrodeposition_pump_speed": 10,
    "electrodeposition_data_path":'..Data/Electrodeposition',
    "electrodeposition_filling_speed": 0.2,

    "reaction_current": 28.2743339,
    "reaction_time": 15 * 60,
    "reaction_catholyte_volume": 20,
    "reaction_anolyte_volume": 20,
    "reaction_pump_speed": 10,
    "reaction_filling_speed": 0.2,
    "reation_data_path":'..Data/Reaction',

    "electrodisolution_time": 600,
    "electrodisolution_catholyte_volume": 20,
    "electrodisolution_anolyte_volume": 20,
    "electrodisolution_pump_speed": 10,
    "electrodisolution_filling_speed": 0.2,
    "electrodisolution_data_path":'..Data/Electrodisolution',

    "aliquot_volume": 0.02,
    "detection_reagent_1_volume": 0.2,
    "detection_reagent_2_volume": 0.1,
    "detection_reagent_3_volume": 0.02,
    "aliquot_filling_speed": 0.1,
    "vial_full_volume": 0.8,

    "wash_flow_cell_volume": 10,
    "wash_flow_cell_time": 120,
    "wash_flow_cell_speed": 16,
    "wash_flow_cell_repeats":2,
    "wash_flow_cell_filling_speed":0.5,
    "wash_flow_cell_wash_comp_repeats":1,
    "wash_flow_cell_wash_comp_volume":10,
    "wash_flow_cell_wash_comp_speed":0.5,
    "wash_flow_cell_wash_comp_speed_last_empty":0.1,

    "wash_vial_repeats": 8,
    "wash_vial_volume": 0.8,
    "wash_vial_speed": 0.4,
    "wash_vial_last_empty": 0.1,

    "wash_compartment_repeats":4,
    "wash_compartment_volume":10,
    "wash_compartment_speed":0.4,
    "wash_compartment_speed_last_empty":0.1,

    "syringe_wash_repeats": 5,
    "syringe_wash_speed": 0.6,
    "syringe_wash_volume_RX": 1.5,
    "syringe_wash_volume_AZ": 0.8,
    "air_compensation_volume": 0.025,
    "air_flush_factor":2,
    "air_flush_speed":10,
    
    "syringe_initialization_speed":0.4
}
# 'stock' == port leading to a stock solution, None == whatever other purpose intended for that port
CONNECTIONS_INFO = {
    'tecanAZ01': {
        "waste": {'port': 9, 'volume': 1, 'usage': None},
        "valveAZ01": {'port': 8, 'volume': 0.09, 'usage': None},
        "WEvial02": {'port': 7, 'volume': 0.18, 'usage': None},
        "WEvial01": {'port': 6, 'volume': 0.18, 'usage': None},
        "uv-vis": {'port': 5, 'volume': 8, 'usage': None},
        "d3": {'port': 4, 'volume': 0.115, 'usage': 'stock'},
        "d2": {'port': 3, 'volume': 0.1, 'usage': 'stock'},
        "d1": {'port': 2, 'volume': 0.1, 'usage': 'stock'},
        "water": {'port': 1, 'volume': 0.47, 'usage': 'stock'}
    },
    'valveAZ01': {
        "waste": {'port': 10, 'volume': 1, 'usage': None},
        "vial9": {'port': 9, 'volume': 0.26, 'usage': None},
        "vial8": {'port': 8, 'volume': 0.26, 'usage': None},
        "vial7": {'port': 7, 'volume': 0.27, 'usage': None},
        "vial6": {'port': 6, 'volume': 0.285, 'usage': None},
        "vial5": {'port': 5, 'volume': 0.275, 'usage': None},
        "vial4": {'port': 4, 'volume': 0.28, 'usage': None},
        "vial3": {'port': 3, 'volume': 0.28, 'usage': None},
        "vial2": {'port': 2, 'volume': 0.285, 'usage': None},
        "vial1": {'port': 1, 'volume': 0.26, 'usage': None}
    },
    'tecanRX01': {
        "waste": {'port': 12, 'volume': 2.5, 'usage': None},
        "WEvial02": {'port': 11, 'volume': 0.2, 'usage': None},
        "CEvial02": {'port': 10, 'volume': 0.175, 'usage': None},
        "WEvial01": {'port': 9, 'volume': 0.18, 'usage': None},
        "CEvial01": {'port': 8, 'volume': 0.17, 'usage': None},
        "valveRX01": {'port': 7, 'volume': 0.09, 'usage': None},
        "anolyte": {'port': 6, 'volume': 0.37, 'usage': 'stock'},
        "air": {'port': 5, 'volume': 0.55, 'usage': 'stock'},
        "Cu": {'port': 4, 'volume': 0.4, 'usage': 'stock', 'composition': 'Cu', 'concentration': 0.1},
        "Ni": {'port': 3, 'volume': 0.4, 'usage': 'stock', 'composition': 'Ni', 'concentration': 0.1},
        "Co": {'port': 2, 'volume': 0.32, 'usage': 'stock', 'composition': 'Co', 'concentration': 0.1},
        "water": {'port': 1, 'volume': 0.64, 'usage': 'stock'}
    },
    'valveRX01': {
        "waste": {'port': 10, 'volume': 2.5, 'usage': None},
        "acid": {'port': 9, 'volume': 0.42, 'usage': 'stock'},
        "elyte8": {'port': 8, 'volume': 0.42, 'usage': 'stock', 'composition': 'NaNO3', 'concentration': 0.1},
        "elyte7": {'port': 7, 'volume': 0.42, 'usage': 'stock', 'composition': 'KNO3', 'concentration': 0.1},
        "elyte6": {'port': 6, 'volume': 0.39, 'usage': 'stock', 'composition': 'LiNO3', 'concentration': 0.1},
        "elyte5": {'port': 5, 'volume': 0.39, 'usage': 'stock', 'composition': 'Ca(NO3)2', 'concentration': 0.1},
        "elyte4": {'port': 4, 'volume': 0.39, 'usage': 'stock', 'composition': 'Mg(NO3)2', 'concentration': 0.1},
        "elyte3": {'port': 3, 'volume': 0.37, 'usage': 'stock', 'composition': 'NaCl', 'concentration': 0.1},
        "elyte2": {'port': 2, 'volume': 0.37, 'usage': 'stock', 'composition': 'NaBr', 'concentration': 0.1},
        "elyte1": {'port': 1, 'volume': 0.37, 'usage': 'stock', 'composition': 'NaI', 'concentration': 0.1}
    }
}
for instrument in CONNECTIONS_INFO:
    CONFIG_COMPONENTS[instrument]['ports'] = {port: CONNECTIONS_INFO[instrument][port]['port'] for port in CONNECTIONS_INFO[instrument]}
CONFIG_SETUP_1 = ['potentiostat01', 'valve01', 'tecanAZ01', 'tecanRX01', 'longerCE01', 'longerWE01']
