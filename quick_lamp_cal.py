from autoammonia.hardware.uv_vis_module import acquire_spectrum
import matplotlib.pyplot as plt
from autoammonia.hardware.uv_vis_module import lamp_switch
from autoammonia.hardware.syringe_pumps import syringe_draw_and_dispense
import time


df = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time=0.10, dark=False)
plt.figure(figsize=(10, 5))
plt.plot(df['Wavelength (nm)'], df['Intensity'])
plt.xlabel('Wavelength (nm)')
plt.ylabel('Intensity')
plt.title('Lamp Calibration')
plt.show()
