from Amonia_SDL_v02 import mix_metals
from tecan_pumps import draw_and_dispense_tecan_func
from prefect import flow

@flow
def printer(c):
    print('Printing :',c)

if __name__=='__main__':
    """draw_and_dispense_tecan_func.serve(
            name='draw_dispense',
            parameters = {'syringe_pump':'tecanRX01','volume':1,'draw_valve_port':'Cu','dispense_valve_port':'waste','speed':1,'wait':0,'kwargs':{}})"""
    mix_metals.serve(
        name='mix_metals_trial',
        tags=['mixing_precursors'],
        pause_on_shutdown = True,
        parameters = {'syringe_pump':'tecanRX01','metal_ratios':[1,1,1], 'deposition_volume':1,'kwargs':{},}
    )
    #mix_metals(syringe_pump = 'tecanRX01', metal_ratios = [1,1,1], deposition_volume = 1)
    """printer.serve(
            name='dummy_test',
            tags = ['test'],
            pause_on_shutdown = True,
            parameters = {'c':'Hello world'}
            )"""
