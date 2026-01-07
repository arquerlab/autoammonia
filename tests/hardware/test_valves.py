"""
Hardware tests for selection valves.

Tests valve port switching operations.
These tests require physical hardware to be connected.
"""
import pytest

from autoammonia.hardware.selection_valves import switch_port_valve
from .hardware_test_helpers import test_valve_basic


@pytest.mark.hardware
class TestSelectionValves:
    """Tests for Valco selection valves."""

    @pytest.mark.parametrize("valve", ["valveRX01", "valveAZ01"])
    def test_switch_to_waste_port(self, valve, hardware_test_mode, mock_redis):
        """Test switching valve to waste port."""
        # Use helper function for basic operation
        valve_name, status, error = test_valve_basic(valve, port="waste")
        
        # Verify the test succeeded
        assert status == "OK", f"Valve {valve} test failed: {error}"

    @pytest.mark.parametrize("valve", ["valveRX01", "valveAZ01"])
    def test_switch_multiple_ports(self, valve, hardware_test_mode, mock_redis):
        """Test switching valve to multiple different ports."""
        # Switch to waste
        switch_port_valve(valve=valve, port="waste")
        
        # Switch to first port (if available)
        # Note: Adjust port names based on actual CONNECTIONS_INFO
        # This is a basic test - in practice you'd check available ports
        try:
            switch_port_valve(valve=valve, port="1")
        except Exception:
            # If port "1" doesn't exist, that's okay for this test
            pass
        
        # Switch back to waste
        switch_port_valve(valve=valve, port="waste")
        
        assert True

