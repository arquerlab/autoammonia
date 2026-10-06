import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

folder = r'C:\Users\LAB-CO2MAP\ammonia_data\uvvis'
folder_ca = r'C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis'
experiment_id = 84

data = []
spectra_data = []

for file in os.listdir(folder):
    if file.endswith('.csv') and f'ID{experiment_id}' in file:
        
        path = os.path.join(folder, file)
        df_uv = pd.read_csv(path)
        df_uv['Abs_zero'] = df_uv['Absorption'] - df_uv['Absorption'].iloc[-1]
        df_uv['Abs_zero_filtered'] = df_uv['Abs_zero'].rolling(window=12).mean()

        # Peak in 635–695 nm
        df_filtered = df_uv[df_uv['Wavelength (nm)'].between(635, 695)]
        intensity = df_filtered['Abs_zero'].max()
        print('Absorbance: ', intensity)
        print('Wavelength at max absorbance: ', df_filtered['Wavelength (nm)'].iloc[df_filtered['Abs_zero'].argmax()])

        # Store absorbance spectrum in 450-850 nm for plotting
        df_spectrum = df_uv[df_uv['Wavelength (nm)'].between(530, 850)]

        # Extract time (seconds)
        time = int(file.split('_')[1].split('RXT')[1].split('.')[0])

        data.append({
            "file": file,
            "time_s": time,
            "absorbance": intensity
        })

        spectra_data.append({
            "time_s": time,
            "spectrum": df_spectrum
        })

for file in os.listdir(folder_ca):
    if file.endswith('.csv') and f'{experiment_id}' in file and 'CA' in file:
        path = os.path.join(folder_ca, file)
        df_ca = pd.read_csv(path)
        print('Average current: ', df_ca['Current (A)'].mean()*5)

plt.figure()
plt.plot(df_ca['Time (s)'], df_ca['Current (A)'])
plt.xlabel("Time (s)")
plt.ylabel("Current (A)")
plt.close()

df = pd.DataFrame(data)
df = df.sort_values("time_s").reset_index(drop=True)

print(df)
# UV-Vis absorbance spectra
plt.figure()
for item in sorted(spectra_data, key=lambda x: x["time_s"]):
    spectrum = item["spectrum"]
    plt.plot(
        spectrum["Wavelength (nm)"],
        spectrum["Abs_zero"],
        label=f'{item["time_s"]} s'
    )
    plt.plot(
        spectrum["Wavelength (nm)"],
        spectrum["Abs_zero_filtered"],
        label=f'{item["time_s"]} s (filtered)'
    )
    plt.legend()
plt.xlabel("Wavelength (nm)")
plt.ylabel("Absorbance")
plt.show()