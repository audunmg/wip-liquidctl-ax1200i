#!/usr/bin/env python3


import os
import serial
from select import select
from binascii import hexlify

from liquidctl.pmbus import CommandCode as CMD
from liquidctl.pmbus import linear_to_float, float_to_linear11


_decode_table = tuple(b'0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10 !\x00\x12"#\x00\x00\x00\x00\x00\x00\x00\x00\x00\x14$%\x00\x16&\'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18()\x00\x1a*+\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1c,-\x00\x1e./\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')

_encode_table = tuple(b'UVYZefij\x95\x96\x99\x9a\xa5\xa6\xa9\xaa')


class CorsairAxPsu(fd):
    """ Corsair AX series power supply unit """

    def __init__():
        pass

    def data_read_dongle(self,fd,size=512):
        if (size < 0):
            size = 512
        size *= 2
        
        # select([fd],[],[],1)

        r = fd.read(size)
        return decode_answer(r )

    def data_write_dongle(self,fd,datain):
        data = encode_answer(0,datain)
        #print(hexlify(data, ' ').decode())
        return fd.write(data)
        

    def decode_answer(self,data):
        # Half of data
        # ret = bytes(len(data)/2)
        if not ((_decode_table[ data[0] ] & 0xf) >> 1) == 7:
            raise (ValueError("Wrong reply data!"))
        ret = b''
        for i in range(1,len(data)-1,2):
            ret += bytes(
                    [(_decode_table[data[i]] & 0xF) | ((_decode_table[data[i + 1]] & 0xF) << 4)]
                )
        #print(ret)
        return ret

    def encode_answer(self,command, data):
        #ret = list(bytes(len(data)*2+2)) # Double size + 2 bytes, a command byte and 0x00 on the end
        ret = bytes([ _encode_table[(command << 1) & 0xF] & 0xFC])
        
        for i in data:
            ret += bytes([_encode_table[i & 0xf]])
            ret += bytes([_encode_table[i >> 4 ]])
        ret += b'\x00'
        return ret

    def convert_byte_float(self, data):
        """ liquidctl.pmbus.linear_to_float does this instead now """
        p1 = (data[1] >> 3) & 31
        if p1 > 15:
            p1 -= 32
        p2 = p2 = (data[1] & 7) * 256 + data[0]
        if p2 > 1024:
            p2 = -1 * (65536 - (p2 | 63488))
        return p2 * (2.0**p1)

    def convert_float_byte(self, val, exp):
        """ liquidctl.pmbus.float_to_linear11 does this instead now """
        p1 = 0
        ret = [0, 0]
        if val > 0.0:
            p1 = int(val * (2.0**exp))
            if p1 > 1023:
                p1 = 1023
        else:
            p2 = int(val * (2.0**exp))
            if p2 < -1023:
                p2 = -1023
            p1 = p2 & 2047
        ret[0] = p1 & 255
        if exp <= 0:
            exp *= -1
        else:
            exp = 256 - exp
        exp = exp << 3 & 255
        ret[1] = p1 >> 8 & 255 | exp
        return bytes(ret)



    def read_dongle_name(self, fd):
        data_write_dongle(fd, b'\x02' )
        return data_read_dongle(fd,512)[:-1].decode()  # eat \x00 at the end there

    def read_dongle_version(self, fd):
        data_write_dongle(fd, b'\x00' )
        ret = data_read_dongle(fd, 5)
        return float((ret[1] >> 4) + (ret[1] & 0xF)) / 10.0

    def _read_data_psu(self, fd, register, length):
        # reg 0x9a, len 7
        d1 = bytes((19, 3, 6, 1, 7, length, register ))
        data_write_dongle(fd, d1)
        ret = data_read_dongle(fd, 2)
        # Seems to be always empty.

        d2 = bytes((8, 7, length))
        data_write_dongle(fd, d2)
        ret = data_read_dongle(fd, length + 1)
        return ret

    def write_data_psu(self, fd, register, length):
        cmd = bytes((0x13,1,4,length+1, register, 0))
        # FIXME finish up



    def read_psu_type(self, fd):
        return read_data_psu(fd, CMD.MFR_MODEL, 7).decode()

    def read_psu_current(self, fd):
        return 

    def send_init(self, fd):
        # Mystery init code from https://github.com/Hagbard-Celin/cpsumon/commit/2e2ecc4d24a9b807bb71fe79d797786edb3365b4
        init_seq = b'\x11\x02\x64\x00\x00\x00\x00'
        return data_write_dongle(fd, init_seq)


    def init_dongle(self, fd):
        retry = 3
        done = 0
        if not send_init(fd):
            raise Exception("oh no")




    def setup_dongle(self, fd):
        print( "Dongle name: {}".format( read_dongle_name(fd) ))

        # Wonder what this is
        d = (17, 2, 100, 0, 0, 0, 0)
        data_write_dongle(fd, d )
        ret = data_read_dongle(fd, 1)

        print( "Mysterious reply: {}".format(hexlify(ret).decode()))

        print( "Dongle Version: {}".format( read_dongle_version(fd) ))

        print( "PSU type: {}".format( read_psu_type(fd) ))


    def _get_float(self, command):
        return linear_to_float(self.read_data_psu(fd, command, 2))
    

    def get_status(self, fd):















if __name__ == "__main__":
    ser = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)
    setup_dongle(ser)
