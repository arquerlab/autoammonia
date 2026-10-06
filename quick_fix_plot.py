import pandas as pd
import matplotlib.pyplot as plt
path = r"C:\Users\LAB-CO2MAP\autoammonia_data\147_cell01_method_CP.csv"
df = pd.read_csv(path)
#Index * 0.00036s
print(len(df))
time_acumulated = []
for i in range(len(df)):
    time_acumulated.append(i * 0.00036)
df['Time_acumulated'] = time_acumulated
print(df['Time_acumulated'])
print(df)
fig, ax = plt.subplots(1,2)
ax[0].plot(df['Time_acumulated'], df['Current (A)'])
ax[0].set_xlabel('Time (s)')
ax[0].set_ylabel('Current (A)')
ax[0].set_title('Current vs Time')
ax[1].plot(df['Potential (V)'], df['Current (A)'])
ax[1].set_xlabel('Potential (V)')
ax[1].set_ylabel('Current (A)')
ax[1].set_title('Potential vs Current')
plt.show()