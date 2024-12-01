import os
import os.path
import queue
import threading
import csv
from typing import Optional, List

import minimalmodbus

import numpy as np
import pandas as pd
from time import time_ns
import matplotlib.pyplot as plt
import datetime


class PotentiometerCommand:
    CMD_SENSOR_ZERO = 0xE0
    CMD_RESET = 0xE1
    CMD_LOADDFLT = 0xE2
    CMD_SET_TIA_GAIN = 0xE3
    CMD_SET_SWITCH = 0xE4
    CMD_FIFO_START = 0xE5
    CMD_PID_START = 0xE6
    CMD_TEST_STOP = 0xE7
    CMD_CLEAR_FIFO = 0xE8
    CMD_CFG_SAVE = 0xF0

    GAIN_1K = 0
    GAIN_10K = 1
    GAIN_100K = 2
    GAIN_1M = 3
    GAIN_10M = 4

    def __init__(self, device) -> None:
        self.device = device
        self.data_queue = queue.Queue()


    def send_potentiometer_command(self,
                                command: int,
                                parameter:int,
    )-> None:
        """
        Sends a specific command and its associated parameter to the potentiometer device
        via Modbus communication using the MinimalModbus library.

        Parameters:
        command (int): The command to be sent to the device, represented as an integer value.
                       This can be one of the predefined constants in the PotentiometerCommand class.
        parameter (int): The parameter associated with the command, represented as an integer value.
                         The meaning of the parameter depends on the specific command.

        Raises:
        minimalmodbus.SlaveReportedException: If the device responds with an error, an exception will be raised.

        Example:
        pot_command.SenPotentiometerCommand(PotentiometerCommand.CMD_SET_TIA_GAIN, PotentiometerCommand.GAIN_10K)
        """
        try:
            self.device.write_registers(0x4F00, [command, parameter])
        except minimalmodbus.SlaveReportedException as wr_err:
            print(f"{wr_err} Sending test start.\n")
            exit()


    def read_write_data_pid_active(self,
                                   current: float,
                                   time: float,
                                   tia_gain: Optional[int] = 0,
                                   reducing_factor: Optional[int] = 5,
                                   n_register: Optional[int] = 120,
    )->None:
        """
        Function that handles the sending commands to the potentiostat and reading
        the output data when using the PID of the potentiostat to apply a fix current.
        The output data is added progressively to the 'data_queue'.

        Args:
            current (float): Current to be applied (in A).
            time (float): Time for the current to be applied (in sec).
            tia_gain (Optional[int]): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm].
                This parameter is generally referred in commercial potentiostats as current/potential range.
            reducing_factor (Optional[int]): Factor for reducing data size. Ej, a reducing factor of 2 will average
                every two points to reduce data size to half. Defaults to 5.
            n_register (Optional[float]): Size of data packages sent to the potentiostat. Defaults to 120.

        Behaviour:
            - The current input is converted from np.float32 to uint16
            - The Transimpedance amplifier gain (TIA_GAIN) is initialized to the specified resistance. The FIFO
              is cleared and PID is switch on (which will switch already the FIFO).
            - The write and reading of data is performed in a loop until the time exceeds the input time of
              the measurement. In this loop, a try-except clause is used for both writing and reading. No delays for 
              writing or reading are applied.
            - When read, the output data is converted back from uint16 to np.float32 and added to 'data_queue'.
            - Optionally, before adding the data, a reducing factor can be applied to the data to RAM collapsing
              over time.
            - The 'data_queue' consist of a np.ndarray: A numpy array where each element is a pair of float values:
              [potential (in V), current (in A)]
            - Once the measurement is finished, potentiostat is switched off and adc_data list is returned.

        Notes:
            - Select the TIA_GAIN carefully according to you expected current range of the reaction. If the gian is
              higher than needed (lower resistance), a higher noise level will be assumed unnecessarily. But if the
              gain is set too low (higher resistance), the desired current might not be reached.
            - Unexpected behaviour is observed in first iterations of the while loop: number of reading operations is 
              lower than writing operations. Reading seems to fail for arround 1 to 5 times during first 0.1s.
              For that reason, delays to both operations were removed, which improves the situation but does not solve it.
        """

        params = {'busy_dly_ns': 400e6, 'wr_err_cnt': 0, 'rd_err_cnt': 0, 'wr_dly_st': 0,
                  'rd_dly_st': 0, 'rx_tx_reg': 0, 'transmission_st': time_ns()}

        #Get target value in uint16
        total_time = 0
        target = np.array([current], dtype=np.float32)
        target = target.tobytes(order='C')
        target = np.frombuffer(target, np.uint16)
        target = target.tolist()

        #Activate everything and clear fifo
        self.send_potentiometer_command(self.CMD_SET_TIA_GAIN, tia_gain)
        self.send_potentiometer_command(self.CMD_CLEAR_FIFO, 1)
        self.send_potentiometer_command(self.CMD_SET_SWITCH, 1)

        #Start sending/collecting
        while total_time < time:
            st = time_ns()
            try:
                try: # This has been modified since last time, need to be tested properly
                    if (st - params['wr_dly_st']) > params['busy_dly_ns']:
                        self.device.write_registers(0x4F00, [self.CMD_PID_START] + target)  # Send data
                        params['wr_err_cnt'] = 0
                except minimalmodbus.SlaveReportedException:
                    params['wr_dly_st'] = time_ns()
                    params['wr_err_cnt'] += 1

                # We need read two times for each write time because adc push two values to FIFO
                for r in range(0, 2):
                    if (st - params['rd_dly_st']) > params['busy_dly_ns']:
                        rd_data = self.device.read_registers(0x100,
                                                             n_register)  # Collect data
                        # Data conversion from uint16 to np.float32
                        adc_words = np.array(rd_data).astype(np.uint16)
                        adc_bytes = adc_words.tobytes()
                        rd_list = np.frombuffer(adc_bytes, np.float32)
                        rd_list = np.reshape(rd_list, (-1, 2))

                        if reducing_factor is not None:
                            reduced_data = []
                            pkg_num = len(rd_list)//reducing_factor
                            pkg_len = len(rd_list)//pkg_num
                            for i in range(pkg_num):
                                start = i * pkg_len
                                end = (i + 1) * pkg_len if i != (pkg_num - 1) else len(rd_list)
                                block = rd_list[start:end]
                                mean_block = np.mean(block, axis=0)
                                reduced_data.append(mean_block)
                            rd_list = reduced_data
                        
                        self.data_queue.put(rd_list)
                    else:
                        break
            except minimalmodbus.SlaveReportedException:
                params['rd_dly_st'] = time_ns()
                params['rd_err_cnt'] += 1
            total_time += (time_ns() - st) / 1000000000 #Time passed

        #Switch off
        self.send_potentiometer_command(self.CMD_SET_SWITCH, 0)
        self.send_potentiometer_command(self.CMD_TEST_STOP, 1)
        result_tm = (time_ns() - params['transmission_st']) / 1e9
        data_rate = (2 * params['rx_tx_reg']) / result_tm
        print(f"\nTotal transmission time {result_tm:3.4} s, data rate {(data_rate / 1000):3.4} KBytes/s.\n")


    def read_write_data_pid_inactive(self,
                                     potential: float,
                                     time: float,
                                     tia_gain: Optional[int] = 0,
                                     reducing_factor: Optional[int] = None,
                                     n_register: int = 120,
    ) -> None:
        """
        Function that handles sending commands to the potentiostat and reading the output data when using the PID
        of the potentiostat to apply a fixed potential. The output data is added progressively to the 'data_queue'.

        Args:
           potential (float): Potential to be applied (in V).
           time (float): Time for the potential to be applied (in sec).
           tia_gain (Optional[int]): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm].
                This parameter is generally referred in commercial potentiostats as current/potential range.
           reducing_factor (Optional[int]): Factor for reducing data size. Ej, a reducing factor of 2 will average
                every two points to reduce data size to half. Defaults to 5.
           n_register (Optional[int]): Size of data packages sent to the potentiostat. Defaults to 120.

        Behaviour:
           - From the input potential, a numpy array is generated with a given length, assuming 0.2 ms interval
             between points. The array is then converted from np.float32 to uint16.
           - The Transimpedance amplifier gain (TIA_GAIN) is initialized to the specified resistance. Then FIFO
             and potentiostat are switched.
           - The writing and reading of data is performed in a loop until all the data list created is sent.
             In this loop, a try-except clause is used for both writing and reading. No delays for writing or reading
             are applied.
           - When reading, the output data is converted back from uint16 to np.float32 and added to 'data_queue'.
           - Optionally, before adding the data, a reducing factor can be applied to the data to RAM collapsing
             over time.
           - The 'data_queue' consist of a np.ndarray: A numpy array where each element is a pair of float values:
             [potential (in V), current (in A)]
           - Once the measurement is finished, potentiostat is switched off and adc_data list is returned.

        Notes:
           - Select the TIA_GAIN carefully according to your expected potential range of the reaction. If the gain
             is higher than needed (lower resistance), a higher noise level will be assumed unnecessarily. But if the
             gain is set too low (higher resistance), the desired potential might not be reached.
           - Unexpected behaviour is observed in first iterations of the while loop: number of reading operations is 
             lower than writing operations. Reading seems to fail for arround 1 to 5 times during first 0.1s.
             For that reason, delays to both operations were removed, which improves the situation but does not solve it.
        """

        params = {'busy_dly_ns': 400e6, 'wr_err_cnt': 0, 'rd_err_cnt': 0, 'wr_dly_st': 0,
                  'rd_dly_st': 0, 'rx_tx_reg': 0, 'transmission_st': time_ns()}

        # Generate numpy array to send
        t_point = 0.00036 # Interval of 0.4 ms
        len_data = int(time // t_point)
        y = np.full(len_data, potential, dtype=np.float32)
        y_bytes = y.tobytes(order='C')
        write_list = np.frombuffer(y_bytes, np.uint16)
        print(f"Write list element count {len(write_list)}.\n")
        n_items = len(write_list)

        #Activate everything
        self.send_potentiometer_command(self.CMD_SET_TIA_GAIN, tia_gain)
        self.send_potentiometer_command(self.CMD_FIFO_START, 1)
        self.send_potentiometer_command(self.CMD_SET_SWITCH, 1)

        # Send and collect data
        i = 0
        params['transmission_st']=time_ns()
        while i < n_items:
            st = time_ns()
            data = write_list[i:i + n_register].tolist()
            try:
                if (st - params['wr_dly_st']*0) > params['busy_dly_ns']:
                    self.device.write_registers(0x200, data)
                    params['wr_err_cnt'] = 0
                    i += n_register
                    params['rx_tx_reg'] += n_register
            except minimalmodbus.SlaveReportedException:
                params['wr_dly_st'] = time_ns()
                params['wr_err_cnt'] += 1
            try:
                # We need read two times for each write time becase adc push two values to FIFO
                for r in range(0, 2):
                    if (st - params['rd_dly_st']*0) > params['busy_dly_ns']:
                        rd_data = self.device.read_registers(0x100,
                                                             n_register)  # Registernumber, number of decimals
                        
                        # Data conversion from uint16 to np.float32
                        adc_words = np.array(rd_data).astype(np.uint16)
                        adc_bytes = adc_words.tobytes()
                        rd_list = np.frombuffer(adc_bytes, np.float32)
                        rd_list = np.reshape(rd_list, (-1, 2))

                        if reducing_factor is not None:
                            reduced_data = []
                            pkg_num = len(rd_list)//reducing_factor
                            pkg_len = len(rd_list)//pkg_num
                            for i in range(pkg_num):
                                start = i * pkg_len
                                end = (i + 1) * pkg_len if i != (pkg_num - 1) else len(rd_list)
                                block = rd_list[start:end]
                                mean_block = np.mean(block, axis=0)
                                reduced_data.append(mean_block)
                            rd_list = reduced_data

                        self.data_queue.put(rd_list)
                        params['rx_tx_reg'] += n_register
                        params['rd_err_cnt'] = 0
                    else:
                        break
            except minimalmodbus.SlaveReportedException:
                params['rd_dly_st'] = time_ns()
                params['rd_err_cnt'] += 1

        # Switch off
        self.send_potentiometer_command(self.CMD_SET_SWITCH, 0)
        self.send_potentiometer_command(self.CMD_TEST_STOP, 1)
        result_tm = (time_ns() - params['transmission_st']) / 1e9
        data_rate = (2 * params['rx_tx_reg']) / result_tm
        print(f"\nTotal transmission time {result_tm:3.4} s, data rate {(data_rate / 1000):3.4} KBytes/s.\n")

    
    def saving_func(self, filepath: str) -> None:
        """
        Handles the saving of data to a CSV file as items are added to the 'data_queue'.

        Args:
            filepath (str): The path where the CSV file will be created and the data will be stored.

        Behaviour:
            - Opens the specified CSV file in write mode.
            - Continuously retrieves items from the 'data_queue'.
            - Buffers retrieved items until the buffer size exceeds 20.
            - Writes the buffered data to the CSV file in batches using the 'save_batch' method.
            - Flushes the file to ensure data is saved periodically.
            - Stops processing when a 'None' item is retrieved from the queue, signaling the end of input.
            - Writes any remaining buffered items to the file before closing it.
        """
        buffer = []
        with open(filepath, mode="w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            while True:
                item = self.data_queue.get()
                if item is None:
                    break
                buffer.append(item)
                if len(buffer) > 20:
                    self.save_batch(buffer, writer)
                    buffer.clear()
                    csv_file.flush()
            if buffer:
                self.save_batch(buffer, writer)
                csv_file.flush()
        print('Saving finished')
    
    
    @staticmethod
    def save_batch(batch: List, writer: csv.writer):
        """
        Writes a batch of data to a CSV file using the provided writer object.

        Args:
            batch (list): A list of items, where each item is expected to be iterable (e.g., a list or tuple of rows).
            writer (csv.writer): A CSV writer object used to write rows to the file.
        """
        for p in batch:
            for sp in p:
                writer.writerow(sp)
    
    
    def apply_ca(self,
                 potential: float,
                 time: float,
                 tia_gain: Optional[int] = 0,
                 filepath: Optional[str] = None,
                 plot: Optional[bool] = False,
    )->None:
        """
        Method for applying a chrono-amperometry.

        Args:
            potential (float): Potential to be applied (in V).
            time (float): Time for the potential to be applied (in sec).
            tia_gain (Optional[int]): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm]. Defaults to 0.
                This parameter is generally referred in commercial potentiostats as current/potential range.
            filepath (Optional[str]): Path where data is meant to be stored. Default to current folder, standard filename
                including experimental conditions, date and time.
            plot (Optional[bool]): Option to plot the result after measurement competition. Defaults to False.
           
        Behaviour:
            - Generates a default file path if none is provided, formatted as:
              `{timestamp}_CA_{potential}_{time}_tia{tia_gain}.csv`.
            - Starts two threads:
                1. `writing_reading_thread`: Handles data collection and writes it to the shared queue.
                2. `saving_thread`: Saves data from the queue to the specified CSV file.
            - Ensures both threads complete by using `.join()` to synchronize them.
            - Signals the end of the saving thread by adding `None` to the data queue.
            - If `plot` is True, calls the `plot` method with the generated or provided file path.
        """
        if filepath is None:
            filepath = f'Data/{datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss%z")}_CA_{potential}_{time}_tia{tia_gain}.csv'
            if os.path.exists('Data'):
                os.makedir('Data')
        
        writing_reading_thread = threading.Thread(target=self.read_write_data_pid_inactive,
                                                  args=(potential, time, tia_gain))
        saving_thread = threading.Thread(target=self.saving_func, args=filepath)

        writing_reading_thread.start()
        saving_thread.start()
        
        writing_reading_thread.join()
        self.data_queue.put(None)
        saving_thread.join()

        if plot: self.plot(filepath)

    def apply_cp(self,
                 current: float,
                 time: float,
                 tia_gain: Optional[int] = 0,
                 filepath: Optional[str] = None,
                 plot: Optional[bool] = False,
    ) -> None:
        """
        Method for applying a chrono-potentiometry.

        Args:
            current (float): Current to be applied (in A).
            time (float): Time for the current to be applied (in sec).
            tia_gain (Optional[int]): Gain resistance to use in the transimpedance amplifier. Integers from
                0 to 4 refer to the different resistance from 1 k[Ohm] to 10 M[Ohm]. Defaults to 0.
                This parameter is generally referred in commercial potentiostats as current/potential range.
            filepath (Optional[str]): Path where data is meant to be stored. Default to current folder, standard filename
                including experimental conditions, date and time.
            plot (Optional[bool]): Option to plot the result after measurement competition. Defaults to False.
        
        Behaviour:
            - Generates a default file path if none is provided, formatted as:
              `{timestamp}_CP_{potential}_{time}_tia{tia_gain}.csv`.
            - Starts two threads:
                1. `writing_reading_thread`: Handles data collection and writes it to the shared queue.
                2. `saving_thread`: Saves data from the queue to the specified CSV file.
            - Ensures both threads complete by using `.join()` to synchronize them.
            - Signals the end of the saving thread by adding `None` to the data queue.
            - If `plot` is True, calls the `plot` method with the generated or provided file path.
        """
        filepath = filepath if filepath is not None else f'{datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss%z")}_CP_{current}_{time}_tia{tia_gain}.csv'
        
        writing_reading_thread = threading.Thread(target= self.read_write_data_pid_active, args=(current,time,tia_gain))
        saving_thread = threading.Thread(target=self.saving_func)
        
        writing_reading_thread.start()
        saving_thread.start()
        
        writing_reading_thread.join()
        self.data_queue.put(None)
        saving_thread.join()
        
        if plot: self.plot(filepath)


    @staticmethod
    def plot(filepath: str):
        """
        Plots data from a CSV file, displaying two subplots for potentiostat ADC captures.

        Args:
            filepath (str): Path to the CSV file containing the data to be plotted.

        Behaviour:
            - Reads the CSV file into a DataFrame using pandas.
            - Creates a figure with two vertically aligned subplots.
            - Plots the first column (WEOUT) in red on the first subplot.
            - Plots the second column (REOUT) in blue on the second subplot.
            - Sets axis labels and colors for better visualization.
            - Displays the plot in a blocking mode to ensure it remains visible until closed by the user.
        """
        data = pd.read_csv(filepath, header=None)
        fig, axs = plt.subplots(2, sharex=True)
        fig.suptitle('Potentiostat ADCs capture.')
        ax1_col = 'tab:red'
        ax2_col = 'tab:blue'
        axs[0].set_ylabel('WEOUT', color=ax1_col)
        axs[0].plot(data[data.columns[0]], color=ax1_col)
        axs[1].set_ylabel('REOUT', color=ax2_col)
        axs[1].plot(data[data.columns[1]], color=ax2_col)
        plt.show(block=False)

"""potentiostat = minimalmodbus.Instrument('COM4', 1)  # port name, slave address (in decimal)
cmd = PotentiometerCommand(potentiostat)
potentiostat.serial.baudrate = 1500000     # Baud
potentiostat.serial.timeout  = 0.03         # seconds
period = 0
cmd.apply_cp(-0.0025,10,0)"""



