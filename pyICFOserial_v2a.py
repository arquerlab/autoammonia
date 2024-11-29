#!/usr/bin/python
# -*- coding: utf-8 -*-
 
import os
import sys
import serial
import binascii

def func_send(input_send,ser):
        try:
                ser.read() #Para comprobar que el puerto esta abierto.
        except:
                print("Error, the port is not open")
                return b''
        else:
                r=b''
                send = b''
                input_send = input_send.split()
                if len(input_send)!=0:
                        #print("Sent:    ",end="")
                        pass
                for i in input_send: ##control para discernir decimal,hexa,binario
                        if '#' in i: break
                        elif len(i)==1:
                                x=int(i).to_bytes(1,'big')
                                send=send+x
                                #print(binascii.b2a_hex(x), end=" ")
                        elif 'D' in i[1]:
                                sub_send=i.split("D")
                                x=int(sub_send[1]).to_bytes(int(sub_send[0]),'big')
                                send=send+x
                                #print(binascii.b2a_hex(x), end=" ")
                        elif 'H' in i[1]:
                                sub_send=i.split("H")
                                x=int(sub_send[1],16).to_bytes(int(sub_send[0]),'big')
                                send=send+x
                                #print(binascii.b2a_hex(x), end=" ")
                        elif 'b' in i[1]:
                                sub_send=i.split("b")
                                x=int(sub_send[1],2).to_bytes(int(sub_send[0]),'big')
                                send=send+x
                                #print(binascii.b2a_hex(x), end=" ")
                        else:     
                                if int(i) > 65535:
                                        x=int(i).to_bytes(3,'big')
                                        send=send+x
                                        #print(binascii.b2a_hex(x), end=" ")
                                elif int(i) > 255:
                                        x=int(i).to_bytes(2,'big')
                                        send=send+x
                                        #print(binascii.b2a_hex(x), end=" ")
                                else:
                                        x=int(i).to_bytes(1,'big')
                                        send=send+x
                                        #print(binascii.b2a_hex(x), end=" ")
                if(send!=b''):
                        ser.write(send)
                        r=ser.read(10000)
                        #print("\nReceived:  ",binascii.b2a_hex(r))
                return str(binascii.b2a_hex(r))

def func_load(archivo,ser):
        archivo = open(archivo, "r")
        r=""
        for linea in archivo.readlines():
                if(linea[0]=="#"):
                        pass
                else:
                        rr=func_send(linea,ser)
                        try:
                                r=r+rr+"\n"
                        except:
                                return 'ERROR'
        archivo.close()
        return r

def func_open(config):
        config = config.split()
        try:
                ser = serial.Serial(config[0],int(config[1]), parity=serial.PARITY_EVEN, timeout=1)
        except:
                print("Error when opening the port")
        else:
                #print("Port opened")
                return ser

def func_close(ser):
        try:
                ser.close()
        except:
                print("Error when closing the port")
        else:
                #print("Port closed")
                pass
        

if __name__ == '__main__':
        while True:
                if(len(sys.argv) > 2):
                        ser = serial.Serial(sys.argv[1],int(sys.argv[2]),parity=serial.PARITY_EVEN, timeout=1) #config serial
                        if sys.argv[3] == "send":
                                func_send(sys.argv[4:],ser)
                        elif sys.argv[3] == "load":
                                func_load(sys.argv[4],ser)
                        else:
                                print("Error, third argument is not correct (send o load)")
                        ser.close()
                        break              
                else:
                        inp = input("ICFOserial>> ")
                        inp = inp.split(" ",1)
                        if inp[0]=="open":
                                serial=func_open(inp[1])          
                        elif inp[0]=="send":
                                func_send(inp[1],serial)
                        elif inp[0]=="load":
                                func_load(inp[1],serial)
                        elif inp[0]=="close":
                                func_close(serial)
                        elif inp[0]=="help":
                                print("open\nsend\nload\nclose\nexit")                
                        elif inp[0]=="exit":
                                break
                        else:
                                print("help to see comandos...\nPress eneter to continue")

