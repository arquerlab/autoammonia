from typing import List, Tuple, Optional
def convert_and_validate_input(input_str: str, is_compositions: bool = True) -> List[List[Tuple[str, float]]]:
    """
    Converts and validates a user input string into a controlled list of (name, value) tuples for compositions or electrolytes.

    Args:
        input_str (str): The input string provided by the user. It can represent a single experiment (as a dictionary or list)
                         or multiple experiments (as a list of dictionaries or lists).
        is_compositions (bool): Flag indicating whether the input is for compositions (True) or electrolytes (False).

    Returns:
        List[List[Tuple[str,float]}]: A nested list of tuples where each tuple contains a valid compound or electrolyte
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
    elif isinstance(input_data, list):
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
        tuple_list = [(name, float(value)) for name, value in zip(_valid_list, new_list)]
        output_data.append(tuple_list)

    return output_data
print(convert_and_validate_input('[1,1,1]', is_compositions=True))