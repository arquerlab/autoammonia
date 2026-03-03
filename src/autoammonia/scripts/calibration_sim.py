import os

from ..calibration import main as calibration_main


def main() -> None:
    """
    Run the calibration flow in simulation mode.

    Sets AUTOAMMONIA_SIMULATION=true so that configuration and components
    use the simulation defaults and mock hardware classes, then invokes
    the standard calibration entry point.
    """
    os.environ["AUTOAMMONIA_SIMULATION"] = "true"
    os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)

    calibration_main()


if __name__ == "__main__":
    main()

