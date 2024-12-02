import redis

from default_config import DEFAULT_CONFIG

client = redis.StrictRedis(
        host="adrastea",
        port=6379,
        password="potato12",
        decode_responses=True
        )

def client_initialization(**kwargs)->None:
        config = {**DEFAULT_CONFIG,**kwargs}
        parallel_cells = config['parallel_cells']

        # Variables to track filled and empty vials
        client.rpush('empty_vials', *['vial1', 'vial2', 'vial3', 'vial4', 'vial5', 'vial6', 'vial7', 'vial8'])
        client.delete('filled_vials')
        
        for cell in range(1,parallel_cells+1):
                cell_str = str(cell).zfill(2)
                # Variables to track volume on each compartment
                client.set(f'WEvial{cell_str}_volume', 0)
                client.set(f'CEvial{cell_str}_volume', 0)
                # Variables to track reaction status on eacch cell
                client.set(f'flowcell{cell_str}_reaction_catholyte','')
                client.set(f'flowcell{cell_str}_reaction_metal_ratios','')

        # Variables to track reaction status and safety
        client.set('reaction_status', 'waiting')
        client.set('flow_cell_content', 'clean')
        client.set('safety_operation', 1)
        # Variables to track pump status
        client.set('longerWE01', '0')
        client.set('longerCE01', '0')