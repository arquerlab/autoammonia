"""
Hardware tests for UV-Vis spectrometer and lamp.

Tests lamp switching and spectrum acquisition.
These tests require physical hardware to be connected.
"""
import pytest
import pandas as pd

from autoammonia.hardware.uv_vis_module import lamp_switch, acquire_spectrum


@pytest.mark.hardware
class TestUVVisLamp:
    """Tests for UV-Vis lamp."""

    def test_lamp_switch_on_off(self, hardware_test_mode, mock_redis):
        """Test switching lamp on and off."""
        # Turn lamp on
        lamp_switch(lamp='lamp01', on=True)
        
        # Turn lamp off
        lamp_switch(lamp='lamp01', on=False)
        
        # If we get here without exception, the operation succeeded
        assert True

    def test_lamp_switch_cycle(self, hardware_test_mode, mock_redis):
        """Test multiple on/off cycles."""
        for _ in range(2):
            lamp_switch(lamp='lamp01', on=True)
            lamp_switch(lamp='lamp01', on=False)
        
        assert True


@pytest.mark.hardware
class TestSpectrometer:
    """Tests for UV-Vis spectrometer."""

    def test_acquire_spectrum(self, hardware_test_mode, mock_redis):
        """Test acquiring a spectrum with lamp (using acquire_spectrum which handles lamp)."""
        # acquire_spectrum automatically handles lamp on/off
        spectrum = acquire_spectrum(
            spectrometer='UVVIS01',
            lamp='lamp01',
            integration_time=1.0
        )
        
        # Verify spectrum is a DataFrame
        assert isinstance(spectrum, pd.DataFrame), "Spectrum should be a pandas DataFrame"
        assert len(spectrum) > 0, "Spectrum should contain data"
        
        # Check for expected columns
        assert "Wavelength (nm)" in spectrum.columns, "Spectrum should have 'Wavelength (nm)' column"
        assert "Intensity" in spectrum.columns, "Spectrum should have 'Intensity' column"

