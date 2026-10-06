import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score

folder = r'C:\Users\LAB-CO2MAP\autoammonia_data\calibration'
concentrations = [0.5, 0.25, 0.1, 0.05, 0.025, 0.01, 0.005, 0.0025, 0.001]
concentrations = concentrations[::-1]
absorption_values = []
concentration_values = []

fig, ax = plt.subplots(1, 2)
ax[0].set_xlabel('Wavelength (nm)')
ax[0].set_ylabel('Absorption')
ax[1].set_xlabel('Wavelength (nm)')
ax[1].set_ylabel('Absorption')
ax[1].set_title('Calibration')

for file in os.listdir(folder):
    if file.endswith('.csv') and len(file) < 20:
        df = pd.read_csv(os.path.join(folder, file))
        concentration = concentrations[int(file[-5])-1]
        #Add noise filter for absorption values
        df['Absorption_filtered'] = df['Absorption'].rolling(window=3).mean()
        df['Absorption_filtered'] = df['Absorption_filtered'] - df['Absorption_filtered'].iloc[-1]
        if concentration < 0.5:
            #Get max absorption in 635-695 nm range
            df_filtered = df[df['Wavelength (nm)'].between(635, 695)]
            absorbance = df_filtered['Absorption_filtered'].max()
            if concentration in [0.25, 0.1, 0.025, 0.005]:
                concentration_values.append(concentration)
                absorption_values.append(absorbance)
            print(file, concentration, absorbance)
            ax[0].plot(df['Wavelength (nm)'], df['Absorption_filtered'], label=f'{concentration} mg/L')
ax[0].set_ylim(-0.1, 2.5)
ax[0].set_xlim(400, 850)
ax[0].legend()

ax[1].set_xlabel('Concentration (mg/L)')
ax[1].set_ylabel('Absorption')
#Fit a line to the data
for concentration, adsorbance in zip(concentration_values, absorption_values):
    ax[1].plot(concentration, adsorbance, 'o')
ax[1].legend()
fit = np.polyfit(concentration_values, absorption_values, 1)
#Plot the fit
ax[1].plot(concentration_values, np.polyval(fit, concentration_values))
#Print the fit
print(f'y = {fit[0]:.2f}x + {fit[1]:.2f}')
#Print the R2 score
r2 = r2_score(concentration_values, absorption_values)
ax[1].text(0.5, 0.5, f'y = {fit[0]:.2f}x + {fit[1]:.2f},\n R2 = {r2:.2f}', transform=ax[1].transAxes)
print(f'R2 = {r2:.2f}')
plt.show()