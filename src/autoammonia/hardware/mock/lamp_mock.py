from abc import ABC, abstractmethod
import threading
import time

# --- Mock Arduino ---
class ArduinoMock:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.commands_sent = []
        print(f"[MockArduino] Initialized on port {port} with baudrate {baudrate}")

    def rotate_motor(self, angle: int):
        print(f"[MockArduino] Rotating motor to {angle} degrees")
        self.commands_sent.append(f"rotate:{angle}")

    def send_pulse(self):
        print("[MockArduino] Sending pulse")
        self.commands_sent.append("pulse")

    def close(self):
        print("[MockArduino] Closed connection")

# --- Abstract Lamp base class ---
class LampMock(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

# --- Mock MotorSwitchLamp ---
class MotorSwitchLampMock(LampMock):
    def __init__(self, arduino: ArduinoMock, on_degrees: int = 50, off_degrees: int = 0):
        self.arduino = arduino
        self.on_degrees = on_degrees
        self.off_degrees = off_degrees
        self.started = False

    def start(self):
        print(f"[MockMotorSwitchLamp] Switching motor ON to {self.on_degrees}° then OFF to {self.off_degrees}°")
        self.arduino.rotate_motor(self.on_degrees)
        self.arduino.rotate_motor(self.off_degrees)
        self.started = True

    def stop(self):
        print("[MockMotorSwitchLamp] Stopping (calling start again)")
        self.start()

# --- Mock PulsedLamp ---
class PulsedLampMock(LampMock):
    def __init__(self, arduino: ArduinoMock, pulse_interval: float = 0.5):
        self.arduino = arduino
        self.pulse_interval = pulse_interval
        self._running = False
        self._thread = None
        self.pulse_count = 0

    def _pulse_loop(self):
        print("[MockPulsedLamp] Pulse loop started")
        while self._running:
            self.arduino.send_pulse()
            self.pulse_count += 1
            time.sleep(self.pulse_interval)
        print("[MockPulsedLamp] Pulse loop stopped")

    def start(self):
        print("[MockPulsedLamp] Starting pulsed lamp")
        self._running = True
        self._thread = threading.Thread(target=self._pulse_loop)
        self._thread.start()

    def stop(self):
        print("[MockPulsedLamp] Stopping pulsed lamp")
        self._running = False
        if self._thread:
            self._thread.join()
