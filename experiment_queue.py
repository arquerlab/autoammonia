import json
import ast
from typing import List, Dict, Union

from redis_client import client
from default_config import CONNECTIONS_INFO
from decorators import with_lock
from utils import reset_cache, get_valid_precursors, get_valid_electrolytes

_valid_compounds: List[str] = []
_valid_electrolytes: List[str] = []

def convert_and_validate_input(input_str: str, is_compositions: bool = True) -> List[List[float]]:
    """
    Converts and validates a user input string into a controlled list format for compositions or electrolytes.

    Args:
        input_str (str): The input string provided by the user. It can represent a single experiment (as a dictionary or list)
                         or multiple experiments (as a list of dictionaries or lists).
        is_compositions (bool): Flag indicating whether the input is for compositions (True) or electrolytes (False).

    Returns:
        List[List[float]]: A nested list where each sublist corresponds to an experiment. Each sublist contains numerical values
                           (floats or integers) representing the quantities of valid compositions or electrolytes.

    Raises:
        ValueError: If:
            - The input string cannot be parsed.
            - The input format is invalid (not a dictionary, list, or list of dictionaries/lists).
            - The number of values does not match the expected number of valid compositions or electrolytes.
            - At least one value in a sublist is not a number (int or float).
            - All values in a sublist are zero (at least one non-zero value is required).
    """
    try:
        input_data = ast.literal_eval(input_str)
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Invalid input format: {e}")

    if is_compositions:
        _valid_list = _valid_compounds
    else:
        _valid_list = _valid_electrolytes
    
    if isinstance(input_data, dict):
        input_data = [input_data]
    elif isinstance(input_data,list):
        if all(isinstance(item, (int, float)) for item in input_data):
            input_data = [input_data]
    else:
        raise ValueError("Invalid input format")
    for item in input_data:
        new_list = []
        if isinstance(item, dict):
            for compound in _valid_list:
                new_list += [item[compound] if compound in item else 0]
        else:
            new_list = item
        if len(new_list) != len(_valid_list):
            raise ValueError(f"Input list must contain exactly {len(_valid_list)} values.")
        all_0 = True
        for ratio in new_list:
            if not isinstance(ratio, (int, float)):
                raise ValueError("Invalid input, all values must be integers or floats")
        for ratio in new_list:
            all_0 = all_0 and ratio==0
        if all_0:
            raise ValueError("Invalid input, at least one value must be higher than 0")

    return new_list


def generate_experiments(compositions: List[List[float]],
                         electrolytes: List[List[float]]) -> List[Dict[str, List[float]]]:
    """
    Generates all possible combinations of experiments between compositions and electrolytes.

    Args:
        compositions (List[List[float]]): A list of compositions, where each composition is represented as a list of numerical values (floats or ints),
                                          corresponding to the quantities of valid compounds.
        electrolytes (List[List[float]]): A list of electrolyte sets, where each electrolyte set is a list of numerical values (floats or ints),
                                          corresponding to the quantities of valid electrolytes.

    Returns:
        List[Dict[str, Dict[str, float]]]: A list of experiments, where each experiment is represented as a dictionary with the keys:
            - 'composition': A dictionary mapping valid compound names (e.g., from `_valid_compounds`) to their quantities.
            - 'electrolyte': A dictionary mapping valid electrolyte names (e.g., from `_valid_electrolytes`) to their quantities.
    """
    experiments = []
    for composition_set in compositions:
        for electrolyte_set in electrolytes:
            experiments.append({
                'composition': composition_set,
                'electrolyte': electrolyte_set
            })
    return experiments

@with_lock(acquisition_timeout=5,function_timeout=5)
def enqueue_experiment(list_name: str, data: dict) -> None:
    """
    Enqueues the experiment data into the Redis queue for further processing.

    Args:
        list_name (str): Redis variable where experiments will be added.
        data (dict): A dictionary containing the experiment data to be enqueued.

    Raises:
        Exception: If there is an error when sending the data to Redis.
    """
    try:
        task = json.dumps(data)
        client.lpush(list_name, task)
        print("Experiment data enqueued successfully.\n", task)
    except Exception as e:
        print(f"Error sending data to Redis: {e}")
    print("Current queue state:")
    print(client.lrange(list_name, 0, -1))


def main() -> None:
    """
    Main function to interact with the user, gather input for compositions and electrolytes,
    validate the inputs, generate experiments, and enqueue the experiment data into Redis.
    """
    global _valid_compounds
    global _valid_electrolytes
    while True:
        reset_cache()
        _valid_compounds, _ = get_valid_precursors()
        _valid_electrolytes, _ = get_valid_electrolytes()

        while True:
            try:
                compositions = convert_and_validate_input(
                    input(f'Type compositions desired. Precursors available: {_valid_compounds} \n'),
                    is_compositions=True)
                print('Input sent: ', compositions)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        while True:
            try:
                electrolytes = convert_and_validate_input(input('Type electrolyte desired. Electrolytes available: \n'
                                                           f'{_valid_electrolytes} \n'), is_compositions=False)
                print('Input sent: ',electrolytes)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        try:
            experiments = generate_experiments(compositions, electrolytes)
            for experiment in experiments:
                enqueue_experiment("experiment_queue",experiment)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()

