import asyncio
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pyBEEP import PotentiostatController, PotentiostatDevice

folder = r"C:\Users\LAB-CO2MAP\Documents\beep_test"
file_path = folder + r"\test0.csv"
device = PotentiostatDevice(port='COM22', address=1)
controller = PotentiostatController(device = device)
controller.apply_measurement(mode='CP', params={'current': -0.001, 'duration': 10}, folder=folder, filename='test0.csv')
df = pd.read_csv(file_path)
fig, ax = plt.subplots(1,2)
ax[0].plot(df['Time (s)'], df['Current (A)'])
ax[0].set_xlabel('Time (s)')
ax[0].set_ylabel('Current (A)')
ax[0].set_title('Current vs Time')
ax[1].plot(df['Potential (V)'], df['Current (A)'])
ax[1].set_xlabel('Potential (V)')
ax[1].set_ylabel('Current (A)')
ax[1].set_title('Potential vs Current')
plt.show()