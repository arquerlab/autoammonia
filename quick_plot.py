import pandas as pd
import matplotlib.pyplot as plt
from pyBEEP import PotentiostatController, PotentiostatDevice
experiment_id = 64
folder = r'C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis'
try:
    df_prerx = pd.read_csv(f'{folder}/{experiment_id}_cell01_method_LSV_prerx.csv')
except FileNotFoundError:
    print(f"File {experiment_id}_cell01_method_LSV_prerx.csv not found")
    df_prerx = None
try:
    df_postrx = pd.read_csv(f'{folder}/{experiment_id}_cell01_method_LSV_postrx.csv')
except FileNotFoundError:
    print(f"File {experiment_id}_cell01_method_LSV_postrx.csv not found")
    df_postrx = None
if df_prerx is not None:
    plt.plot(df_prerx['Potential (V)'], df_prerx['Current (A)'])
if df_postrx is not None:
    plt.plot(df_postrx['Potential (V)'], df_postrx['Current (A)'])
plt.show()
try:
    df_ca = pd.read_csv(f'{folder}/{experiment_id}_cell01_method_CA.csv')
except FileNotFoundError:
    print(f"File {experiment_id}_cell01_method_CA.csv not found")
    df_ca = None
if df_ca is not None:
    plt.plot(df_ca['Time (s)'], df_ca['Current (A)'])
plt.show()