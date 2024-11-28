import serial
from time import sleep

from redis.cluster import command

from pyICFOserial_v2a import *

def hex2complement(number, ty=4):
    if ty == 4:
        hexadecimal_result = format(number, "03X")
        return hexadecimal_result.zfill(4)
    elif ty == 2:
        hexadecimal_result = format(number, "02X")
        return hexadecimal_result.zfill(1)


def XOR(command):
    a = command[1:]
    curr = int(a[0], 16)
    for i in range(1, len(a)):
        curr = curr ^ int(a[i], 16)
    return hex2complement(curr, 2)


def modifier(command):
    for i in range(1, len(command)):
        if command[i] == 'E8':
            command.insert(i + 1, '00')
        if command[i] == 'E9':
            command[i] = 'E8'
            command.insert(i + 1, '01')
    return command


def get_RS(speed, pump=None, start_stop=None, direct=None):
    # converting information to appropriate hexidecimal
    hex_speed = hex2complement(int(speed * 10))  # is a string
    hex_pump = hex2complement(int(pump), 2)  # is a string

    hex_direct = None  # is a string
    if direct == False:
        hex_direct = hex2complement(1, 2)
    else:
        hex_direct = hex2complement(0, 2)

    # constructing the command
    command = ['E9', hex_pump, '06', '57', '4A', hex_speed[0:2], hex_speed[2:4], start_stop, hex_direct]
    new_command = modifier(command)
    xor = XOR(new_command)
    new_command.insert(len(new_command), xor)

    # converting the list to hexidecimals that can be outputted
    # final = bytes(int(x, base=16) for x in new_command)  ##codigo GUI version, anterior
    pairs = [new_command[i:i + 2] for i in range(0, len(new_command), 2)]
    final = " ".join(f"2H{''.join(pair)}" for pair in pairs)

    return final

def hex2int(comand):
    return int(comand, 16)

class Longer_BT100_3J_Pump():
    def __init__(self,
                 com_port: str,
                 address: int,
                 tube_ID: float = 3.2,
                 baudrate: int = 1200,
                 parity = serial.PARITY_EVEN,
                 stopbits = serial.STOPBITS_ONE,
                 bytesize = serial.EIGHTBITS,
                 timeout: float = 0.2,
                 direction: bool = True,
                 top_speed: int = 100):
        self.com_port = com_port
        self.address = address
        self.tube_ID = tube_ID
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.timeout = timeout
        self.direction = direction
        self.top_speed = top_speed
        self.received = str()
    def openport(self, *args):
        config = self.com_port+' '+str(self.baudrate)
        self.serial=func_open(config)
    def closeport(self, *args):
        func_close(self.serial)

    def run(self, speed, direction = None):
        if direction is None:
            direction = self.direction
        out = get_RS(speed , self.address, '01', direction)
        try:
            try:
                self.openport()
            except:
                print("Error when opening the port")
            x = func_send(out, self.serial)
            self.received = x
            self.closeport()
            print("Running Pump")
        except:
            print("Error with the port")
            self.received = "ERROR"
    def stop(self):
        out = get_RS(50, self.address, '00', self.direction)
        #print("PRINTout: ", out)

        try:
            self.openport()
            x = func_send(out, self.serial)
            self.received = x
            self.closeport()
            print("Stopping Pump")
        except:
            print("Error with the port")
            self.received = "ERROR"

    def get_state(self):
        try:
            self.openport()
            hex_address = hex2complement(int(self.address), 2)
            command = ['E9',hex_address, '02', '52', '4A']
            xor = XOR(command)
            command.insert(len(command), xor)
            pairs = [command[i:i + 2] for i in range(0, len(command), 2)]
            out = " ".join(f"2H{''.join(pair)}" for pair in pairs)
            status = func_send(out,self.serial)
            self.received = status
            self.closeport()
            status = status[:-1]
            running, speed, direction = hex2int(status[-6:-4]), hex2int(status[-10:-6]), hex2int(status[-4:-2])
            direction = 1 if direction == 1 else -1
            return running * speed / 10 * direction
        except:
            print('Error getting the state')
            self.received = 'ERROR'
    
    def change_address(self,new_address):
        try:
            self.openport()
            hex_old_address = hex2complement(int(self.address), 2)
            hex_new_address = hex2complement(int(new_address), 2)
            
            command.insert(len(command), xor)
            pairs = [command[i:i + 2] for i in range(0, len(command), 2)]
            out = " ".join(f"2H{''.join(pair)}" for pair in pairs)
            print(out)
            x4 = func_send(out, self.serial)
            print(x)
            self.received = x
            self.closeport()
            self.address = new_address
            print('Pump address has been changed to: ', self.address)
        except:
            print(f'Error when changing the address from {self.address} to {new_address}')




