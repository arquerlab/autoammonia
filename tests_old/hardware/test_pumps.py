"""
Hardware tests for peristaltic and syringe pumps.

Tests pump operations including run, stop, check, draw, and dispense.
These tests require physical hardware to be connected.

Unit tests focus on detailed functionality with assertions, while the
system test (test_all_hardware_components) uses helper functions to
quickly verify all components work together.
"""
import pytest

from autoammonia.hardware.peristaltic_pumps import run_pump, stop_pump, check_pump
from autoammonia.hardware.syringe_pumps import syringe_draw, syringe_dispense
from autoammonia.config.config import DEFAULT_CONFIG
from .hardware_test_helpers import (
    test_peristaltic_pump_basic,
    test_syringe_pump_basic,
)


@pytest.mark.hardware
class TestPeristalticPumps:
    """Tests for Longer peristaltic pumps."""

    @pytest.mark.parametrize("pump", ["longerWE01", "longerCE01"])
    def test_run_and_stop_pump(self, pump, hardware_test_mode, mock_redis):
        """Test running and stopping a peristaltic pump."""
        # Use helper function for basic operation, then add detailed assertions
        pump_name, status, status_value = test_peristaltic_pump_basic(pump)
        
        # Verify the test succeeded
        assert status == "OK", f"Pump {pump} basic test failed: {status_value}"
        assert status_value is not None, "Pump status should be returned"
        
        # Additional detailed test: verify pump can be checked when stopped
        final_status = check_pump(pump=pump)
        assert final_status == 0, f"Pump {pump} should be stopped after test"

    @pytest.mark.parametrize("pump", ["longerWE01", "longerCE01"])
    def test_pump_direction(self, pump, hardware_test_mode, mock_redis):
        """Test pump direction control."""
        # Test forward direction
        run_pump(pump=pump, speed=1.0, direction=True)
        status_forward = check_pump(pump=pump)
        stop_pump(pump=pump)
        
        # Test reverse direction
        run_pump(pump=pump, speed=1.0, direction=False)
        status_reverse = check_pump(pump=pump)
        stop_pump(pump=pump)
        
        # Status should have opposite signs for opposite directions
        assert status_forward > 0, "Forward direction should give positive status"
        assert status_reverse < 0, "Reverse direction should give negative status"

    @pytest.mark.parametrize("pump", ["longerWE01", "longerCE01"])
    def test_check_pump_status(self, pump, hardware_test_mode, mock_redis):
        """Test checking pump status."""
        # Check stopped pump
        status = check_pump(pump=pump)
        assert status == 0, f"Stopped pump {pump} should return status 0"
        
        # Check running pump
        run_pump(pump=pump, speed=2.0, direction=True)
        status = check_pump(pump=pump)
        assert abs(status) > 0, f"Running pump {pump} should return non-zero status"
        stop_pump(pump=pump)


@pytest.mark.hardware
class TestSyringePumps:
    """Tests for Tecan syringe pumps."""

    @pytest.mark.parametrize("pump", ["tecanRX01", "tecanAZ01"])
    def test_syringe_draw_and_dispense(self, pump, hardware_test_mode, mock_redis):
        """Test drawing and dispensing with a syringe pump."""
        # Use helper function for basic operation
        pump_name, status, error = test_syringe_pump_basic(pump, volume=0.05)
        
        # Verify the test succeeded
        assert status == "OK", f"Syringe pump {pump} test failed: {error}"

    @pytest.mark.parametrize("pump", ["tecanRX01", "tecanAZ01"])
    def test_syringe_small_volume(self, pump, hardware_test_mode, mock_redis):
        """Test syringe pump with very small volume."""
        test_volume = 0.01
        test_speed = DEFAULT_CONFIG['syringe_wash_speed']
        
        syringe_draw(
            syringe_pump=pump,
            volume=test_volume,
            valve_port='waste',
            speed=test_speed
        )
        
        syringe_dispense(
            syringe_pump=pump,
            volume=test_volume,
            valve_port='waste',
            speed=test_speed
        )
        
        assert True

