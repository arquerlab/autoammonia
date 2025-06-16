from .config.components_config import CONFIG_COMPONENTS
from .hardware.tecan_pumps import draw_tecan_func, dispense_tecan_func, draw_and_dispense_tecan_func
from .hardware.valco_valve import switch_port_valve
from .config.config import CONNECTIONS_INFO

if __name__ == '__main__':
    for component in CONNECTIONS_INFO:
        skip_component = False
        print(f'Component to use: {component}')
        if 'tecan' in component:
            pump = component
            max_vol = CONFIG_COMPONENTS[component]['syringe_volume']*1000
            print(max_vol)
        if skip_component:
            next
        else:
            for port in CONNECTIONS_INFO[component]:
                if port != 'air_waste' and not skip_component:
                    if 'valve' in component:
                        for _ in range(3):
                            try:
                                switch_port_valve(component, port)
                                break
                            except:
                                pass
                    total_vol = 0
                    print(f'Port to use: {port}')
                    if port == 'valve':
                        input('Disconnect tube from valve and put in an empty container. Press enter to continue.')
                        switch_port_valve(component, 'air_waste')
                    else:
                        input(f'Fill container of {port} with water. Press enter to continue.')
                    while True:
                        vol = input(f'Indicate volume to fill up, or stop for moving forward (acum_vol = {total_vol}): ')
                        if vol == 'stop' or vol == 's' or vol == 'skip':
                            print(f'Port initialized. Total volume: {total_vol}')
                            break
                        elif 'next c' in vol or 'skip c' in vol:
                            print('Skipping component')
                            skip_component = True
                            break
                        elif isinstance(vol, (float, int)):
                            try:
                                vol = float(vol)
                                if abs(vol) > max_vol:
                                    print(vol, max_vol)
                                    raise ValueError
                                if vol>0:
                                    if port == 'valve':
                                        draw_and_dispense_tecan_func(pump, vol, 'water', port, speed=0.005)
                                        total_vol += vol
                                    else:
                                        draw_port = port if 'valve' not in component else 'valve'
                                        draw_tecan_func(pump,vol,draw_port,speed=0.0075)
                                        dispense_tecan_func(pump,vol,'air_waste',speed=1000)
                                        total_vol += vol
                                if vol<0:
                                    if port == 'valve':
                                        draw_and_dispense_tecan_func(pump, abs(vol), port, 'air_waste', speed=1000)
                                        total_vol = 0
                                    else:
                                        dispense_port = port if 'valve' not in component else 'valve'
                                        draw_and_dispense_tecan_func(pump,abs(vol),'air_waste',dispense_port,speed=1000)
                                        total_vol = 0
                            except ValueError:
                                print('Value exceeds the syringe limit, try again.')
                            except Exception as e:
                                print(Exception, e)
                        else:
                            print('Input not valid. Valid entries: \n'
                                  '- "stop", "skip", "s": for passing to next port \n'
                                  '- "skip c...", "next c...": for passing to next pump/valve \n'
                                  '- positive int/float: For dispensing liquid \n'
                                  '- negative int/float: For dispensing air')
