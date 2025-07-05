import json
import ast
from typing import List, Dict, Tuple
from prefect import task, flow

from .utils.redis_client import client
from .utils.decorators import with_lock
from .utils.elytes_precursors import reset_cache, get_valid_precursors, get_valid_electrolytes

_valid_compounds: List[str] = []
_valid_electrolytes: List[str] = []

@task
def convert_and_validate_input(input_str: str, is_compositions: bool = True) -> List[List[Tuple[str, float]]]:
    """
    Converts and validates a user input string into a controlled list of (name, value) tuples for compositions or electrolytes.

    Args:
        input_str (str): The input string provided by the user. It can represent a single experiment (as a dictionary or list)
                         or multiple experiments (as a list of dictionaries or lists).
        is_compositions (bool): Flag indicating whether the input is for compositions (True) or electrolytes (False).

    Returns:
        List[List[Tuple[str,float]]]: A nested list of tuples where each tuple contains a valid compound or electrolyte
                                        name and its corresponding value.

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

    output_data = []
    for item in input_data:
        if isinstance(item, dict):
            new_list = [item.get(compound, 0) for compound in _valid_list]
        else:
            new_list = item
        if len(new_list) != len(_valid_list):
            raise ValueError(f"Input list must contain exactly {len(_valid_list)} values.")
        if not all(isinstance(ratio, (int, float)) for ratio in new_list):
            raise ValueError("Invalid input: all values must be integers or floats")
        if all(ratio == 0 for ratio in new_list):
            raise ValueError("Invalid input: at least one value must be higher than 0")
        tuple_list = [(name, float(value)) for (name, port), value in zip(_valid_list, new_list)]
        output_data.append(tuple_list)

    return output_data

@task
def generate_experiments(compositions: List[List[Tuple[str, float]]],
                         electrolytes: List[List[Tuple[str, float]]]) -> List[Dict[str, List[Tuple[str,float]]]]:
    """
    Generates all possible combinations of experiments between precursors compositions and electrolytes.

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
    try:
        experiments = []
        for composition_set in compositions:
            for electrolyte_set in electrolytes:
                experiments.append({
                    'composition': composition_set,
                    'electrolyte': electrolyte_set
                })
        return experiments
    except Exception as e:
        print(f"Error generating the experiments: {e}")

@task
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
        print("Json dumped")
        client.lpush(list_name, task)
        print("Experiment data enqueued successfully.\n", task)
    except Exception as e:
        print(f"Error sending data to Redis: {e}")
    print("Current queue state:")
    print(client.lrange(list_name, 0, -1))

@flow
def request_experiments() -> None:
    """
    Main function to interact with the user, gather input for compositions and electrolytes,
    validate the inputs, generate experiments, and enqueue the experiment data into Redis.
    """
    global _valid_compounds
    global _valid_electrolytes
    while True:
        reset_cache()
        _valid_compounds = get_valid_precursors()
        _valid_electrolytes = get_valid_electrolytes()

        while True:
            try:
                _valid_compounds_names = ', '.join([compound[0] for compound in _valid_compounds])
                compositions = convert_and_validate_input(
                    input(f'Type compositions desired. Precursors available: {_valid_compounds_names} \n'),
                    is_compositions=True)
                print('Input sent: ', compositions)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        while True:
            try:
                _valid_electrolytes_names = ', '.join([electrolyte[0] for electrolyte in _valid_electrolytes])
                electrolytes = convert_and_validate_input(input('Type electrolyte desired. Electrolytes available: \n'
                                                           f'{_valid_electrolytes_names} \n'), is_compositions=False)
                print('Input sent: ',electrolytes)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        try:
            experiments = generate_experiments(compositions, electrolytes)
            print(f"Experiments generated: {experiments}")
            for experiment in experiments:
                enqueue_experiment("experiment_queue",experiment)
            print("Experiment enqueued")
        except Exception as e:
            print(f"Error adding experiments to queue: {e}")


if __name__ == "__main__":
    request_experiments()

