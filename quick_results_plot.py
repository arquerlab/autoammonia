import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

folder = r'C:\Users\LAB-CO2MAP\ammonia_data\uvvis'
experiment_id = 79
# =========================
# USER INPUTS
# =========================

initial_volume = 8.0      # mL
aliquot_volume = 0.3      # mL
current_A = 0.005         # 5 mA
area_cm2 = 0.2            # electrode area

calibration_factor = 3.7631  # Abs = factor * (mg/L)

# =========================
# CONSTANTS
# =========================

F = 96485        # C/mol
MW_N = 14.0      # g/mol
z = 8            # e- per NH3

# =========================
# EXTRACT DATA
# =========================

data = []
spectra_data = []

for file in os.listdir(folder):
    if file.endswith('.csv') and f'ID{experiment_id}' in file:
        
        path = os.path.join(folder, file)
        df_uv = pd.read_csv(path)

        # Peak in 635–695 nm
        df_filtered = df_uv[df_uv['Wavelength (nm)'].between(635, 695)]
        intensity = df_filtered['Absorption'].max()

        # Store absorbance spectrum in 450-850 nm for plotting
        df_spectrum = df_uv[df_uv['Wavelength (nm)'].between(530, 850)]

        # Convert Abs ? mg/L ? mg/mL
        concentration_mg_mL = (intensity / calibration_factor) / 1000

        # Extract time (seconds)
        time = int(file.split('_')[1].split('RXT')[1].split('.')[0])

        data.append({
            "file": file,
            "time_s": time,
            "conc_mg_mL": concentration_mg_mL
        })

        spectra_data.append({
            "time_s": time,
            "spectrum": df_spectrum
        })

# =========================
# SORT BY TIME
# =========================

df = pd.DataFrame(data)
df = df.sort_values("time_s").reset_index(drop=True)

# =========================
# VOLUME TRACKING
# =========================

n = len(df)

V_remaining = np.zeros(n)
V_remaining[0] = initial_volume

for i in range(1, n):
    V_remaining[i] = V_remaining[i-1] - aliquot_volume

df["V_remaining_mL"] = V_remaining

# =========================
# MASS BALANCE (CRITICAL)
# =========================

N_total_mg = np.zeros(n)
N_removed_mg = 0

for i in range(n):
    conc = df.loc[i, "conc_mg_mL"]

    # Mass currently in reactor
    N_in_reactor = conc * V_remaining[i]

    # Total produced = in reactor + already removed
    N_total_mg[i] = N_in_reactor + N_removed_mg

    # Update removed AFTER measurement
    N_removed_mg += conc * aliquot_volume

df["N_total_mg"] = N_total_mg

# =========================
# FARADAIC EFFICIENCY
# =========================

# mg ? mol NH3
N_total_mol = (df["N_total_mg"] / 1000) / MW_N

# Charge (C)
Q = current_A * df["time_s"]

FE = np.zeros(n)

for i in range(1, n):
    if Q[i] > 0:
        FE[i] = (z * F * N_total_mol[i]) / Q[i]

df["FE_percent"] = FE * 100

# =========================
# PRODUCTION RATE
# =========================

rate_mg_s = np.zeros(n)

for i in range(1, n):
    dt = df.loc[i, "time_s"] - df.loc[i-1, "time_s"]
    dN = df.loc[i, "N_total_mg"] - df.loc[i-1, "N_total_mg"]
    rate_mg_s[i] = dN / dt

df["rate_mg_s"] = rate_mg_s

# =========================
# NORMALIZED METRICS
# =========================

# mg N/s ? mol NH3/s
rate_mol_s = (df["rate_mg_s"] / 1000) / MW_N

# µmol cm?² h?¹
df["rate_umol_cm2_h"] = rate_mol_s * 1e6 * 3600 / area_cm2

# Current density (A/cm²)
j_total = current_A / area_cm2

# Partial current to NH3 (mA/cm²)
df["j_NH3_mA_cm2"] = FE * j_total * 1000

# =========================
# OUTPUT
# =========================

print("\n===== RESULTS =====\n")
print(df)

print("\n===== SUMMARY =====")
print(f"Final FE (%): {df['FE_percent'].iloc[-1]:.2f}")
print(f"Total NH3 (mg N): {df['N_total_mg'].iloc[-1]:.4f}")
print(f"Final rate (µmol cm?² h?¹): {df['rate_umol_cm2_h'].iloc[-1]:.2f}")
print(f"j_NH3 (mA/cm²): {df['j_NH3_mA_cm2'].iloc[-1]:.2f}")

# Save results
df.to_csv(f"NH3_results_ID{experiment_id}.csv", index=False)

# =========================
# PLOTS
# =========================

# NH3 production
plt.figure()
plt.plot(df["time_s"], df["N_total_mg"], 'o-')
plt.xlabel("Time (s)")
plt.ylabel("Total N (mg)")
plt.title("NH3 production")
plt.grid()

# Faradaic efficiency
plt.figure()
plt.plot(df["time_s"], df["FE_percent"], 'o-')
plt.xlabel("Time (s)")
plt.ylabel("FE (%)")
plt.title("Faradaic Efficiency")
plt.grid()

# Production rate
plt.figure()
plt.plot(df["time_s"], df["rate_umol_cm2_h"], 'o-')
plt.xlabel("Time (s)")
plt.ylabel("Rate (µmol cm?² h?¹)")
plt.title("NH3 Production Rate")
plt.grid()

# Partial current density
plt.figure()
plt.plot(df["time_s"], df["j_NH3_mA_cm2"], 'o-')
plt.xlabel("Time (s)")
plt.ylabel("j_NH3 (mA/cm²)")
plt.title("Partial Current Density to NH3")
plt.grid()

# UV-Vis absorbance spectra
plt.figure()
for item in sorted(spectra_data, key=lambda x: x["time_s"]):
    spectrum = item["spectrum"]
    plt.plot(
        spectrum["Wavelength (nm)"],
        spectrum["Absorption"],
        label=f'{item["time_s"]} s'
    )
plt.xlabel("Wavelength (nm)")
plt.ylabel("Absorbance")
#plt.title("Absorbance spectra (450-850 nm)")
#plt.grid()
if len(spectra_data) <= 12:
    plt.legend(frameon=False)

plt.show()