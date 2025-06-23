from typing import List, Tuple
from ..config.config import CONNECTIONS_INFO

_cache = {
    'electrolytes': [],
    'precursors': [],
}

def get_valid_electrolytes() -> List[Tuple[str, str]]:
    """
    Retrieves the list of valid electrolytes from the CONNECTIONS_INFO dictionary.
    The list is cached after the first retrieval for improved performance.

    Returns:
        List[Tuple[str, str]]: A tuple containing:
            - A list of valid electrolytes. If no electrolytes are found, it includes 'water' by default.
            - A list of ports associated with the valid electrolytes.
    """
    global _cache
    if not _cache['electrolytes']:
        _valid_electrolytes = [('water', 'water')]
        for element in CONNECTIONS_INFO:
            if 'RX' in element.upper():
                for port_name, port_dict in CONNECTIONS_INFO[element].items():
                    if 'lyte' in port_name.lower() and 'composition' in port_dict.keys():
                        electrolyte = port_dict['composition']
                        _valid_electrolytes.append(tuple((electrolyte, port_name)))
        _cache['electrolytes'] = _valid_electrolytes
    return _cache['electrolytes']


def get_valid_precursors() -> List[Tuple[str, str]]:
    """
    Retrieves the list of valid precursors from the CONNECTIONS_INFO dictionary.
    The list is cached after the first retrieval for improved performance.

    Returns:
        List[Tuple[str, str]]: A list of tuple containing (precursor, port_name)
    """
    global _cache
    if not _cache['precursors']:
        _valid_precursors = []
        _precursors_ports = []
        for element in CONNECTIONS_INFO:
            if 'RX' in element.upper():
                for port_name, port_dict in CONNECTIONS_INFO[element].items():
                    if 'composition' in port_dict.keys() and 'lyte' not in port_name:
                        compound = port_dict['composition']
                        _valid_precursors.append(tuple((compound, port_name)))
        _cache['precursors'] = _valid_precursors
    return _cache['precursors']


def reset_cache() -> None:
    """
    Resets the cache for valid electrolytes and compounds.
    Clears the cached values for electrolytes, compounds, and their associated ports.
    This ensures that the next time `get_valid_electrolytes` or `get_valid_compounds`
    is called, the data will be reloaded and validated from `CONNECTIONS_INFO`.

    Returns:
        None
    """
    global _cache
    _cache['electrolytes'] = []
    _cache['precursors'] = []
    _cache['electrolytes_ports'] = []
    _cache['precursors_ports'] = []