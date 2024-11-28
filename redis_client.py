import redis

client = redis.StrictRedis(
        host="adrastea",
        port=6379,
        password="potato12",
        decode_responses=True
        )
# Variables to track volume on each compartment
client.set('WE_vial01_volume', 0)
client.set('CE_vial01_volume', 0)
client.set('WE_vial02_volume', 0)
client.set('CE_vial02_volume', 0)
# Variables to track filled and empty vials
client.rpush('empty_vials', *['vial1', 'vial2', 'vial3', 'vial4', 'vial5', 'vial6', 'vial7', 'vial8'])
client.delete('filled_vials')
# Variables to track reaction status and safety
client.set('reaction_catholyte', '')
client.set('reaction_metal_ratios', '')
client.set('reaction_status', 'waiting')
client.set('flow_cell_content', 'clean')
client.set('safety_operation', 1)
# Variables to track pump status
client.set('longerWE01', '0')
client.set('longerCE01', '0')