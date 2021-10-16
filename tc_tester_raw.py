#!/usr/bin/env python

import logging
import os
import sys
import time
import typing
from lib.max31856 import MAX31856, ThermocoupleType
from lib.tempSensor import TempSensorReal
import board
import digitalio
import adafruit_bitbangio
import typing
REG_CR0 = 0x00  # Config Reg 0 - See Datasheet, pg 19
REG_CR1 = 0x01  # Config Reg 1 - averaging and TC type
REG_MASK = 0x02  # Fault mask register (for fault pin)
REG_CJHF = 0x03  # Cold Jcn high fault threshold, 1 degC/bit
REG_CJLF = 0x04  # Cold Jcn low fault threshold, 1 degC/bit
REG_LTHFTH = 0x05  # TC temp high fault threshold, MSB, 0.0625 degC/bit
REG_LTHFTL = 0x06  # TC temp high fault threshold, LSB
REG_LTLFTH = 0x07  # TC temp low fault threshold, MSB, 0.0625 degC/bit
REG_LTLFTL = 0x08  # TC temp low fault threshold, LSB
REG_CJTO = 0x09  # Cold Jcn Temp Offset Reg, 0.0625 degC/bit
REG_CJTH = 0x0A  # Cold Jcn Temp Reg, MSB, 0.015625 deg C/bit (2^-6)
REG_CJTL = 0x0B  # Cold Jcn Temp Reg, LSB
REG_LTCBH = 0x0C  # Linearized TC Temp, Byte 2, 0.0078125 decC/bit
REG_LTCBM = 0x0D  # Linearized TC Temp, Byte 1
REG_LTCBL = 0x0E  # Linearized TC Temp, Byte 0
REG_SR = 0x0F  # Status Register

# // CR0 Configs
CMODE_OFF = 0x00
CMODE_AUTO = 0x80
ONESHOT_OFF = 0x00
ONESHOT_ON = 0x40
OCFAULT_OFF = 0x00
OCFAULT_10MS = 0x10
OCFAULT_32MS = 0x20
OCFAULT_100MS = 0x30
CJ_ENABLED = 0x00
CJ_DISABLED = 0x08
FAULT_AUTO = 0x00
FAULT_MANUAL = 0x04
FAULT_CLR_DEF = 0x00
FAULT_CLR_ALT = 0x02
CUTOFF_60HZ = 0x00
CUTOFF_50HZ = 0x01

# // CR1 Configs
AVG_SEL_1SAMP = 0x00
AVG_SEL_2SAMP = 0x10
AVG_SEL_4SAMP = 0x20
AVG_SEL_8SAMP = 0x30
AVG_SEL_16SAMP = 0x40

B_TYPE = 0x00
E_TYPE = 0x01
J_TYPE = 0x02
K_TYPE = 0x03
N_TYPE = 0x04
R_TYPE = 0x05
S_TYPE = 0x06
T_TYPE = 0x07

# // MASK Configs
CJ_HIGH_MASK = 0x20
CJ_LOW_MASK = 0x10
TC_HIGH_MASK = 0x08
TC_LOW_MASK = 0x04
OV_UV_MASK = 0x02
OPEN_FAULT_MASK = 0x01

try:
    sys.dont_write_bytecode = True
    import config
    sys.dont_write_bytecode = False
except Exception as inst:
    print("Could not import config file.")
    print("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    print(inst)
    exit(1)

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("thermocouple-test")
log.info("Starting thermocouple test")

spi = adafruit_bitbangio.SPI(**config.thermocouples['spi_pins'].asDict())


def read(address):
    buffer = bytearray(length=1)
    spi.readinto(buffer)
    return buffer[0]


cs_pins = []
for chip in config.thermocouples['chips']:
    time.sleep(0.2)
    cs = digitalio.DigitalInOut(chip.cs_pin)
    cs.direction = digitalio.Direction.OUTPUT
    cs.value = True
    cs_pins.append(cs)

pin0 = cs_pins[0]

# select first board
pin0.value = False

spi.write()

time.sleep(0.25)

while True:
    log.info("%d Thresholds: TC: %s , CJ: %s" %
             (0, sensor.temperature_thresholds, sensor.reference_temperature_thresholds,))

    log.info(
        "%d: %0.1f• :> %0.1f"
        % (0, sensor.temperature,
           sensor.reference_temperature))
    log.info(sensor.fault)
    time.sleep(5)
