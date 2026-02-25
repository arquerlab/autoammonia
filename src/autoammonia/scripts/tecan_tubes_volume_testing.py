from ..hardware.syringe_pumps import syringe_draw_and_dispense, syringe_draw, syringe_dispense
from ..hardware.selection_valves import switch_port_valve
from ..config.config import CONNECTIONS_INFO
from ..config.components_config import CONFIG_COMPONENTS

exclude_ports = ["waste", "air","uv_vis"]
def main():
    """Run interactive Tecan tubes volume testing for each tecan pump and its valve."""
    speed = 1000  # Default speed

    # Iterate only over tecan pumps (e.g. tecanAZ01, tecanRX01)
    for pump in CONNECTIONS_INFO:
        if "tecan" not in pump and 'runze' not in pump and 'syringe' not in pump:
            continue

        skip_component = False
        max_vol = CONFIG_COMPONENTS[pump]["syringe_volume"] * 1000
        print(f"\n=== Component to use: {pump} (max syringe volume: {max_vol} µL) ===")

        # Try to find matching valve (e.g. tecanAZ01 -> valveAZ01)
        valve_name = pump.replace("tecan", "valve").replace("runze", "valve").replace("syringe", "valve")
        has_valve = valve_name in CONNECTIONS_INFO

        # 1) Test pump ports (connected directly to containers)
        for port in CONNECTIONS_INFO[pump]:
            if port in exclude_ports or skip_component:
                continue

            total_vol = 0.0
            print(f"\nPump port to use: {port}")
            input(f'Fill container of "{port}" with water. Press Enter to continue.')

            while True:
                vol = input(
                    f'Indicate volume to fill up on "{port}", or "stop" to move forward '
                    f'(acum_vol = {total_vol}): '
                )

                if vol in ("stop", "s", "skip"):
                    print(f'Port "{port}" initialized. Total volume: {total_vol}')
                    syringe_draw_and_dispense(pump, CONFIG_COMPONENTS[pump]["syringe_volume"] * 1000, port, "waste", speed=1000)
                    break
                elif "next c" in vol or "skip c" in vol:
                    print("Skipping component")
                    skip_component = True
                    break
                elif "speed" in vol:
                    try:
                        speed_val = float(vol.split()[1])
                        if 0.001 < speed_val < 1000:
                            speed = speed_val
                            print("Speed set to:", speed)
                        else:
                            print(
                                "Speed not valid. Valid entries:\n"
                                '- "speed <float>": for setting the speed (0.001-1000)\n'
                            )
                    except (ValueError, IndexError):
                        print(
                            "Speed not valid. Valid entries:\n"
                            '- "speed <float>": for setting the speed (0.001-1000)\n'
                        )
                    continue
                else:
                    try:
                        vol_val = float(vol)
                        if abs(vol_val) > max_vol:
                            print(
                                f"Value {vol_val} exceeds syringe limit ({max_vol}), try again."
                            )
                            continue

                        if vol_val > 0:
                            # Draw from this port (container) and send to waste
                            syringe_draw(pump, vol_val, port, speed=speed)
                            syringe_dispense(pump, vol_val, "waste", speed=1000)
                            total_vol += vol_val
                        elif vol_val < 0:
                            # Negative volume: flush line with air/waste
                            syringe_draw_and_dispense(
                                pump, abs(vol_val), "air", port, speed=1000
                            )
                            total_vol = 0
                    except ValueError:
                        print(
                            "Input not valid. Valid entries:\n"
                            '- "stop", "skip", "s": for passing to next port\n'
                            '- "skip c...", "next c...": for passing to next pump/valve\n'
                            '- "speed <float>": for setting the speed\n'
                            "- positive int/float: For dispensing liquid\n"
                            "- negative int/float: For flushing / resetting\n"
                        )
                    except Exception as e:  # noqa: BLE001
                        print(f"Error: {type(e).__name__}: {e}")

        if not has_valve:
            continue
        skip_component = False

        print("\nAll pump ports tested. Moving to valve ports.")

        # 2) Test ports on the matching valve
        for valve_port in CONNECTIONS_INFO[valve_name]:
            if valve_port in exclude_ports or skip_component:
                continue

            total_vol = 0.0
            print(f'\nValve port to use: {valve_port} (valve "{valve_name}")')

            # Route valve to this port, then prime line via pump
            switch_port_valve(valve_name, valve_port)
            input(
                f'Ensure line "{valve_port}" is connected to water. Press Enter to continue.'
            )

            while True:
                vol = input(
                    f'Indicate volume to fill up on valve port "{valve_port}", or "stop" '
                    f'for moving forward (acum_vol = {total_vol}): '
                )

                if vol in ("stop", "s", "skip"):
                    print(
                        f'Valve port "{valve_port}" initialized. Total volume: {total_vol}'
                    )
                    syringe_draw_and_dispense(pump, CONFIG_COMPONENTS[pump]["syringe_volume"] * 1000, 
                    'air', valve_name, speed=1000)
                    break
                elif "next c" in vol or "skip c" in vol:
                    print("Skipping component")
                    skip_component = True
                    break
                elif "speed" in vol:
                    try:
                        speed_val = float(vol.split()[1])
                        if 0.001 < speed_val < 1000:
                            speed = speed_val
                            print("Speed set to:", speed)
                        else:
                            print(
                                "Speed not valid. Valid entries:\n"
                                '- "speed <float>": for setting the speed (0.001-1000)\n'
                            )
                    except (ValueError, IndexError):
                        print(
                            "Speed not valid. Valid entries:\n"
                            '- "speed <float>": for setting the speed (0.001-1000)\n'
                        )
                    continue
                else:
                    try:
                        vol_val = float(vol)
                        if abs(vol_val) > max_vol:
                            print(
                                f"Value {vol_val} exceeds syringe limit ({max_vol}), try again."
                            )
                            continue

                        if vol_val > 0:
                            # Draw from valve port (through valve) and send to waste
                            syringe_draw(pump, vol_val, valve_name, speed=speed)
                            syringe_dispense(pump, vol_val, "waste", speed=1000)
                            total_vol += vol_val
                        elif vol_val < 0:
                            # Flush line connected to this valve port
                            syringe_draw_and_dispense(
                                pump, abs(vol_val), "air", valve_name, speed=1000
                            )
                            total_vol = 0
                    except ValueError:
                        print(
                            "Input not valid. Valid entries:\n"
                            '- "stop", "skip", "s": for passing to next port\n'
                            '- "skip c...", "next c...": for passing to next pump/valve\n'
                            '- "speed <float>": for setting the speed\n'
                            "- positive int/float: For dispensing liquid\n"
                            "- negative int/float: For flushing / resetting\n"
                        )
                    except Exception as e:  # noqa: BLE001
                        print(f"Error: {type(e).__name__}: {e}")

        az_pump = 'tecanAZ01'
        port = 'uv_vis'
        print(f"Testing {az_pump} port {port}")
        while True:
            vol = input(f'Indicate volume to fill up on "{port}", or "stop" to move forward '
                        f'(acum_vol = {total_vol}): ')
            if vol in ("stop", "s", "skip"):
                print(f'Port "{port}" initialized. Total volume: {total_vol}')
                syringe_draw_and_dispense(az_pump, CONFIG_COMPONENTS[az_pump]["syringe_volume"] * 1000, "air", port, speed=1000)
                break
            elif "speed" in vol:
                try:
                    speed_val = float(vol.split()[1])
                    if 0.001 < speed_val < 1000:
                        speed = speed_val
                        print("Speed set to:", speed)
                    else:
                        print(
                            "Speed not valid. Valid entries:\n"
                            '- "speed <float>": for setting the speed (0.001-1000)\n'
                        )
                except (ValueError, IndexError):
                    print(
                            "Speed not valid. Valid entries:\n"
                            '- "speed <float>": for setting the speed (0.001-1000)\n'
                        )
            else:
                try:
                    vol_val = float(vol)
                    if abs(vol_val) > max_vol:
                        print(f"Value {vol_val} exceeds syringe limit ({max_vol}), try again.")
                        continue
                    if vol_val > 0:
                        syringe_draw(az_pump, vol_val, "water", speed=1)
                        syringe_dispense(az_pump, vol_val, port, speed=speed)
                        total_vol += vol_val
                    elif vol_val < 0:
                        syringe_draw_and_dispense(az_pump, abs(vol_val), "air", port, speed=1000)
                        total_vol = 0
                except Exception as e:  # noqa: BLE001
                    print(f"Error: {type(e).__name__}: {e}")

        print("\nAll valve ports tested successfully. Moving to next component.")


if __name__ == '__main__':
    main()
