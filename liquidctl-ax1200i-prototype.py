#!/usr/bin/env python3


import os
import serial
from select import select
from binascii import hexlify

from enum import Enum

from liquidctl.driver.base import BaseDriver
from liquidctl.pmbus import CommandCode as CMD
from liquidctl.pmbus import linear_to_float, float_to_linear11
from datetime import timedelta
from time import sleep

_decode_table = tuple(b'0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10 !\x00\x12"#\x00\x00\x00\x00\x00\x00\x00\x00\x00\x14$%\x00\x16&\'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18()\x00\x1a*+\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1c,-\x00\x1e./\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')

_encode_table = tuple(b'UVYZefij\x95\x96\x99\x9a\xa5\xa6\xa9\xaa')


_SLAVE_ADDRESS = 0x02 # Not used, just copypaste
_CORSAIR_READ_TOTAL_UPTIME = CMD.MFR_SPECIFIC_D1
_CORSAIR_READ_UPTIME = CMD.MFR_SPECIFIC_D2
_CORSAIR_12V_OCP_MODE = CMD.MFR_SPECIFIC_D8
_CORSAIR_READ_OUTPUT_POWER = CMD.MFR_SPECIFIC_EE
_CORSAIR_FAN_CONTROL_MODE = CMD.MFR_SPECIFIC_F0

_RAIL_12V = 0x0
_RAIL_5V = 0x1
_RAIL_3P3V = 0x2
_RAIL_NAMES = {_RAIL_12V: '+12V', _RAIL_5V: '+5V', _RAIL_3P3V: '+3.3V'}
_MIN_FAN_DUTY = 0



# Hoping these are the same
class OCPMode(Enum):
    """Overcurrent protection mode."""

    SINGLE_RAIL = 0x1
    MULTI_RAIL = 0x2

    def __str__(self):
        return self.name.capitalize().replace('_', ' ')


class FanControlMode(Enum):
    """Fan control mode."""

    HARDWARE = 0x0
    SOFTWARE = 0x1

    def __str__(self):
        return self.name.capitalize()



class CorsairAxPsu(BaseDriver):
    """ Corsair AX series power supply unit """

    def __init__(self):
        self.type = ''
        pass

    def data_read_dongle(self,size=512):
        if (size < 0):
            size = 512
        size *= 2
        
        # select([self.fd],[],[],1)

        r = self.fd.read(size)
        return self.decode_answer(r )

    def data_write_dongle(self,datain):
        data = self.encode_answer(0,datain)
        #print(hexlify(data, ' ').decode())
        return self.fd.write(data)
        

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



    def read_dongle_name(self):
        self.data_write_dongle(b'\x02' )
        return self.data_read_dongle(512)[:-1].decode()  # eat \x00 at the end there

    def read_dongle_version(self):
        self.data_write_dongle( b'\x00' )
        ret = self.data_read_dongle(5)
        return float((ret[1] >> 4) + (ret[1] & 0xF)) / 10.0

    def read_pmbus(self, register, length):
        # C read_data_psu
        # reg 0x9a, len 7
        d1 = bytes((0x13, 3, 6, 1, 7, length, register ))
        self.data_write_dongle( d1)
        ret = self.data_read_dongle( 2)
        if not ret == b'':
            raise Exception("Unexpected reply: {}".format(hexlify(ret)))
        # Seems to be always empty.

        d2 = bytes((8, 7, length))
        self.data_write_dongle(d2)
        ret = self.data_read_dongle(length + 1)
        return ret

    def write_pmbus(self, register, data):
        # C write_data_psu
        cmd = bytes((0x13, 1, 4, (len(data) + 1), register, ) + tuple(data))
        #print(hexlify(cmd, ' '))
        self.data_write_dongle( cmd)
        return self.data_read_dongle(1)
        

    def read_psu_model(self):
        # C read_psu_type
        return self.read_pmbus(CMD.MFR_MODEL, 7).decode()


    def send_init(self):
        # Mystery init code from https://github.com/Hagbard-Celin/cpsumon/commit/2e2ecc4d24a9b807bb71fe79d797786edb3365b4
        # Not sure if it is needed?
        init_seq = b'\x11\x02\x64\x00\x00\x00\x00'
        return self.data_write_dongle(init_seq)


    def init_dongle(self):
        retry = 3
        done = 0
        if not send_init():
            raise Exception("oh no")

    def setup_dongle(self ):
        # The other implementation always does this, but it might not be necessary
        print( "Dongle name: {}".format( self.read_dongle_name() ))

        # Wonder what this is
        d = (17, 2, 100, 0, 0, 0, 0)
        self.data_write_dongle( d )
        ret = self.data_read_dongle(1)

        #print( "Mysterious reply: {}".format(hexlify(ret).decode()))

        print( "Dongle Version: {}".format( self.read_dongle_version() ))

        self.type =  self.read_psu_model()
        print( "PSU type: {}".format( self.type ))


    def _get_float(self, command):
        """
        AX1200i supports
        READ_FAN_SPEED_1
        READ_VIN
        READ_IIN

        """
        return linear_to_float(self.read_pmbus( command, 2))

    def _get_timedelta(self,command):
        # This returns a wrong number which increments correctly.
        sec = self.read_pmbus(command, 4)
        return timedelta(seconds=int.from_bytes([sec[2], sec[3], sec[0], sec[1]], byteorder="little"))
    
    def _get_fan_control_mode(self):
        return FanControlMode(self.read_pmbus(_CORSAIR_FAN_CONTROL_MODE, 1)[0])

    def _get_12v_ocp_mode(self):
        return ''
    def _input_power_at(self, input_voltage, output_power):
        def quadratic(params, x):
            a, b, c = params
            return a * x**2 + b * x + c

        for_in115v = quadratic(self.fpowin115, output_power)
        for_in230v = quadratic(self.fpowin230, output_power)

        # interpolate for input_voltage
        return for_in115v + (for_in230v - for_in115v) / 115 * (input_voltage - 115)
 

    def get_status(self ):
        ret = self.write_pmbus(CMD.PAGE, [0])
        if not (ret == b''):
            print("Failed to change page.")

        input_voltage = self._get_float(CMD.READ_VIN)
        input_current = self._get_float(CMD.READ_IIN)
        status = [
            ('Current uptime', self._get_timedelta(_CORSAIR_READ_UPTIME), ''),
            ('Total uptime', self._get_timedelta(_CORSAIR_READ_TOTAL_UPTIME), ''),
            ('Temperature 1', self._get_float(CMD.READ_TEMPERATURE_1), '°C'),
            ('Temperature 2', self._get_float(CMD.READ_TEMPERATURE_2), '°C'),
            ('Fan control mode', self._get_fan_control_mode(), ''),
            ('Fan speed', self._get_float(CMD.READ_FAN_SPEED_1), 'rpm'),
            ('Input voltage', input_voltage, 'V'),
            ('Input current', input_current, 'A'),
            ('+12V OCP mode', self._get_12v_ocp_mode(), ''),
        ]

        for rail in [_RAIL_12V, _RAIL_5V, _RAIL_3P3V]:
            name = _RAIL_NAMES[rail]
            self.write_pmbus(CMD.PAGE, [rail])
            status.append((f'{name} output voltage', self._get_float(CMD.READ_VOUT), 'V'))
            status.append((f'{name} output current', self._get_float(CMD.READ_IOUT), 'A'))
            status.append((f'{name} output power', self._get_float(CMD.READ_POUT), 'W'))

        output_power = self._get_float(_CORSAIR_READ_OUTPUT_POWER)
        input_power = self._get_float(0xee)
        #input_power = round(self._input_power_at(input_voltage, output_power), 0)
        efficiency = round(output_power / input_power * 100, 0)

        status.append(('Total power output', output_power, 'W'))
        status.append(('Estimated input power', input_power, 'W'))
        status.append(('Estimated efficiency', efficiency, '%'))

        self.write_pmbus(CMD.PAGE, [0])
        return status


    def open_dongle(self,dev):
        self.fd = serial.Serial(dev, baudrate=115200, timeout=1)


    def get_12v_rails(self):
        # Should probably be like (2,3,4,5,6)
        channels = (2,3,4,5,6)
        rails = []
        if self.type == 'AX1200i':
            channels = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        if self.type == 'AX1500i':
            channels = (1,2,3)
        for c in channels:
            self.set_page(c, False)
            rail = []
            rail.append(("Voltage", self._get_float(CMD.READ_VOUT), "V"))
            rail.append(("Current", self._get_float(0xe8), "A"))
            rail.append(("Power", self._get_float(0xe9), "W"))
            rail_ocp     = self._get_float(0xea)
            if rail_ocp > 40.0 or rail_ocp == -0.5:
                rail.append(("OCP Mode", False, ''))
                rail.append(("OCP Limit", 40.0, 'A'))
            else:
                if (rail_ocp < 0.0):
                    rail_ocp = 0.0
                rail.append(("OCP Mode", True, ''))
                rail.append(("OCP Limit", rail_ocp, "A"))
            rails.append(rail)
        return rails



    def set_page(self, page, main=True):
        if main == True:
            self.write_pmbus(0x00, [page])
            if not self.read_pmbus(0x00, 1)[0] == page:
                if not self.read_pmbus(0x00, 1)[0] == page:
                    if not self.read_pmbus(0x00, 1)[0] == page:
                        raise Exception("Can't change to page {}".format(page))
        else:
            # Could add a sleep and a loop instead, but it's already so slow.
            self.write_pmbus(0xe7, [page])
            if not self.read_pmbus(0xe7, 1)[0] == page:
                self.write_pmbus(0xe7,[page])
                if not self.read_pmbus(0xe7, 1)[0] == page:
                    if not self.read_pmbus(0xe7, 1)[0] == page:
                        if not self.read_pmbus(0xe7, 1)[0] == page:
                            if not self.read_pmbus(0xe7, 1)[0] == page:
                                raise Exception("Can't change to 12V page {}".format(page))









if __name__ == "__main__":
    psu = CorsairAxPsu()
    psu.open_dongle("/dev/serial/by-id/usb-Silicon_Labs_Corsair_Link_TM_USB_Dongle_R26K0297-if00-port0")
    
    # Print some dongle messages. Necessary? Maybe?
    psu.setup_dongle()
    status =  psu.get_status()
    for l in status:
        print("{:25s}{:>13s} {:<10s}".format(l[0], str(l[1]), l[2]))
    status = psu.get_12v_rails()
    for n in range(0, len(status)):
        print("----- Rail", n)
        for l in status[n]:
            print("{:25s}{:>13s} {:<10s}".format(l[0], str(l[1]), l[2]))


