from Amonia_SDL_v02 import mix_metals, electrodeposition
from tecan_pumps import draw_and_dispense_tecan_func
from prefect import flow

@flow
def testing_electrodep(c):
    mix_metals(syringe_pump='tecanRXX01',metal_ratios=[1,1,1],deposition_volume=8)
    pass

if __name__=='__main__':
    """draw_and_dispense_tecan_func.serve(
            name='draw_dispense',
            parameters = {'syringe_pump':'tecanRX01','volume':1,'draw_valve_port':'Cu','dispense_valve_port':'waste','speed':1,'wait':0,'kwargs':{}})"""
    electrodeposition.serve(
        name='electrodeposition_trial',
        tags=['testing'],
        pause_on_shutdown = True,
        parameters = {'metal_ratios':[1,1,1],'current':-0.005,'time_rx':120,'kwargs':{},}
    )
    #mix_metals(syringe_pump = 'tecanRX01', metal_ratios = [1,1,1], deposition_volume = 1)
    """printer.serve(
            name='dummy_test',
            tags = ['test'],
            pause_on_shutdown = True,
            parameters = {'c':'Hello world'}
            )"""
