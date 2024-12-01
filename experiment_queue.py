import json
import ast
from typing import List, Dict, Union

from redis_client import client
from default_config import CONNECTIONS_INFO

_valid_compounds: List[str] = []
_valid_electrolytes: List[str] = []


def validate_compositions(compositions: List[Dict[str, Union[int, float]]]) -> None:
    """
    Validates that the compositions are a list of dictionaries, each containing exactly 3 compounds with valid amounts.

    Args:
        compositions (List[Dict[str, Union[int, float]]]): A list of compositions, each represented by a dictionary 
                                                           with compound names as keys and amounts as values.

    Raises:
        ValueError: If compositions is not a list, or if any composition does not contain exactly 3 compounds, 
                    or if the compound or amount is invalid.
    """
    if not isinstance(compositions, list):
        raise ValueError("Compositions should be a list.")
    for composition in compositions:
        if not isinstance(composition, dict):
            raise ValueError("Each composition should be a dictionary.")
        if len(composition) != 3:
            raise ValueError("Each composition should contain exactly 3 compounds.")
        for compound, amount in composition.items():
            if compound not in _valid_compounds:
                raise ValueError(f"Invalid compound: {compound}")
            if not isinstance(amount, (int, float)):
                raise ValueError(f"Invalid amount for compound {compound}: {amount}")


def validate_electrolytes(electrolytes: List[List[Dict[str, Union[int, float]]]]) -> None:
    """
    Validates that the electrolytes are a list of lists of dictionaries, each containing valid electrolytes and concentrations.

    Args:
        electrolytes (List[List[Dict[str, Union[int, float]]]]): A list of electrolyte sets, where each set is a list of 
                                                                   dictionaries containing a single electrolyte and its concentration.

    Raises:
        ValueError: If electrolytes is not a list, or if any electrolyte set does not contain dictionaries with 
                    valid electrolyte names and concentrations.
    """
    if not isinstance(electrolytes, list):
        raise ValueError("Electrolytes should be a list.")
    for electrolyte_set in electrolytes:
        if not isinstance(electrolyte_set, list):
            raise ValueError("Each electrolyte set should be a list.")
        for electrolyte in electrolyte_set:
            if not isinstance(electrolyte, dict):
                raise ValueError("Each electrolyte should be a dictionary.")
            if len(electrolyte) != 1:
                raise ValueError("Each electrolyte dictionary should have exactly one key-value pair.")
            name, concentration = list(electrolyte.items())[0]
            if name not in _valid_electrolytes:
                raise ValueError(f"Invalid electrolyte: {name}")
            if not isinstance(concentration, (int, float)):
                raise ValueError(f"Invalid concentration: {concentration}")


def convert_input_to_list(input_str: str, is_compositions: bool = True) -> Union[
    List[Dict[str, Union[int, float]]], List[List[Dict[str, Union[int, float]]]]]:
    """
    Converts user input string into a controlled list, handling specific conversions for compositions and electrolytes.

    Args:
        input_str (str): The input string provided by the user.
        is_compositions (bool): Flag to determine if the input is for compositions (True) or electrolytes (False).

    Returns:
        Union[List[Dict[str, Union[int, float]]], List[List[Dict[str, Union[int, float]]]]]: A list of compositions or electrolytes,
                                                                                       depending on the input.

    Raises:
        ValueError: If the input string cannot be parsed or does not follow the expected format.
    """
    try:
        input_data = ast.literal_eval(input_str)
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Invalid input format: {e}")

    if is_compositions:
        if isinstance(input_data, dict):
            input_data = [input_data]
        elif isinstance(input_data, list) and all(isinstance(i, (int, float)) for i in input_data):
            if len(input_data) == 3:
                input_data = [{_valid_compounds[i]: input_data[i] for i in range(3)}]
            else:
                raise ValueError("Composition list must contain exactly 3 values.")
    else:
        if isinstance(input_data, list) and all(isinstance(i, dict) for i in input_data):
            input_data = [input_data]
        elif isinstance(input_data, dict):
            input_data = [[input_data]]
        elif isinstance(input_data, list) and all(isinstance(i, (int, float)) for i in input_data):
            input_data = [[{_valid_electrolytes[i]: input_data[i]} for i in range(len(input_data))]]
        else:
            raise ValueError("Invalid electrolyte input format.")

    return input_data


def generate_experiments(compositions: List[Dict[str, Union[int, float]]],
                         electrolytes: List[List[Dict[str, Union[int, float]]]]) -> List[
    Dict[str, Union[Dict[str, Union[int, float]], Dict[str, Union[int, float]]]]]:
    """
    Generates all possible combinations of experiments between compositions and electrolytes.

    Args:
        compositions (List[Dict[str, Union[int, float]]]): A list of compositions.
        electrolytes (List[List[Dict[str, Union[int, float]]]]): A list of electrolyte sets.

    Returns:
        List[Dict[str, Union[Dict[str, Union[int, float]], Dict[str, Union[int, float]]]]]: A list of experiments, 
                                                                                     where each experiment is a dictionary 
                                                                                     containing a composition and an electrolyte.
    """
    experiments = []
    for composition in compositions:
        for electrolyte_set in electrolytes:
            for electrolyte in electrolyte_set:
                experiments.append({
                    'composition': composition,
                    'electrolyte': electrolyte
                })
    return experiments


def enqueue_experiment(data: dict) -> None:
    """
    Enqueues the experiment data into the Redis queue for further processing.

    Args:
        data (dict): A dictionary containing the experiment data to be enqueued.

    Raises:
        Exception: If there is an error when sending the data to Redis.
    """
    try:
        task = json.dumps(data)
        client.rpush("experiment_queue", task)
        print("Experiment data enqueued successfully.")
    except Exception as e:
        print(f"Error sending data to Redis: {e}")


def main() -> None:
    """
    Main function to interact with the user, gather input for compositions and electrolytes,
    validate the inputs, generate experiments, and enqueue the experiment data into Redis.
    """
    global _valid_compounds
    global _valid_electrolytes
    while True:
        _valid_compounds = ['Cu', 'Co', 'Ni']
        _valid_electrolytes = []
        for element in CONNECTIONS_INFO:
            if 'RX' in element.upper():
                for port_name, port_dict in CONNECTIONS_INFO[element].items():
                    if 'composition' in port_dict.keys():
                        _valid_electrolytes.append(port_dict['composition'])

        while True:
            try:
                compositions = convert_input_to_list(
                    input(f'Type compositions desired. Compositions available: {_valid_compounds} \n'),
                    is_compositions=True)
                validate_compositions(compositions)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        while True:
            try:
                electrolytes = convert_input_to_list(input('Type electrolyte desired. Electrolytes available: \n'
                                                           f'{_valid_electrolytes} \n'), is_compositions=False)
                validate_electrolytes(electrolytes)
                break
            except ValueError as ve:
                print(f"Validation error: {ve}")

        try:
            experiments = generate_experiments(compositions, electrolytes)
            for experiment in experiments:
                enqueue_experiment(experiment)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()

