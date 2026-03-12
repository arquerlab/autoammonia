import os


def main() -> None:
    """
    Run the calibration flow in simulation mode.

    Sets AUTOAMMONIA_SIMULATION=true so that configuration and components
    use the simulation defaults and mock hardware classes, then imports
    and invokes the standard calibration entry point.

    Note:
        The environment variables are set *before* importing the
        calibration module to ensure that configuration and component
        resolution happen in simulation mode.
    """
    # IMPORTANT: set simulation env vars BEFORE importing modules that load config
    os.environ["AUTOAMMONIA_SIMULATION"] = "true"
    os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)

    # Import lazily so that config picks up the simulation flags
    from ..calibration import main as calibration_main

    calibration_main()


if __name__ == "__main__":
    main()

