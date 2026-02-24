import serial
import time
from abc import ABC, abstractmethod
import threading

class Arduino:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for Arduino reset

    def rotate_motor(self, angle: int):
        """Rotate the motor by the specified degrees (0-180)."""
        self.ser.write(f"{angle}\n".encode())
        self.ser.flush()
        time.sleep(0.2)

    def start_pulses(self, pulse_interval: float):
        """
        Send command to start pulsing with given interval to the Arduino
        Args:
            pulse_interval (float): The interval between pulses in seconds
        """
        self.ser.write(f"START:{pulse_interval}".encode())
        self.ser.flush()
        time.sleep(0.2)

    def stop_pulses(self):
        """Send command to stop pulsing to the Arduino"""
        self.ser.write(b"STOP")
        self.ser.flush()
        time.sleep(0.2)

    def close(self):
        self.ser.close()


class Lamp(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

class MotorSwitchLamp(Lamp):
    def __init__(self, arduino: Arduino, on_degrees: int = 50, off_degrees: int = 0):
        self.arduino = arduino
        self.on_degrees = on_degrees
        self.off_degrees = off_degrees

    def start(self):
        self.arduino.rotate_motor(self.on_degrees)
        time.sleep(3)
        self.arduino.rotate_motor(self.off_degrees)

    def stop(self):
        self.start()

class PulsedLamp(Lamp):
    def __init__(self, arduino: Arduino):
        self.arduino = arduino

    def start(self, pulse_interval: float):
        self.arduino.start_pulses(pulse_interval)
        
    def stop(self):
        self.arduino.stop_pulses()

            