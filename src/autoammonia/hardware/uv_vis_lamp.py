import serial
import time
from abc import ABC, abstractmethod
import threading

class Arduino:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(1)  # Wait for Arduino reset

    def rotate_motor(self, angle: int):
        """Rotate the motor by the specified degrees (0-180)."""
        self.ser.write(f"{angle}\n".encode())

    def send_pulse(self):
        """Send a pulse command to the Arduino (implement as needed)."""
        self.ser.write(b'P')  # Assuming 'P' triggers a pulse in your firmware

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
        self.arduino.rotate_motor(self.off_degrees)

    def stop(self):
        self.start()

class PulsedLamp(Lamp):
    def __init__(self, arduino: Arduino, pulse_interval: float = 0.5):
        self.arduino = arduino
        self.pulse_interval = pulse_interval
        self._running = False
        self._thread = None

    def _pulse_loop(self):
        while self._running:
            self.arduino.send_pulse()
            time.sleep(self.pulse_interval)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._pulse_loop)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            