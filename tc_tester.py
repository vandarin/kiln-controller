#!/usr/bin/env python

import logging
import os
import sys
import time
import typing
from lib.max31856 import MAX31856
from lib.tempSensor import TempSensorReal
import board
import digitalio
import adafruit_bitbangio
import typing


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
print("Starting thermocouple test")

spi = board.SPI()

sensors = []
for chip in config.thermocouples['chips']:
    time.sleep(0.2)
    cs = digitalio.DigitalInOut(chip.cs_pin)
    cs.direction = digitalio.Direction.OUTPUT
    cs.value = True
    sensor = MAX31856(
        spi, cs, chip.tc_type, continuous=True)
    sensors.append(sensor)

for idx, sensor in enumerate(sensors):
    time.sleep(0.2)

    sensor.temperature_thresholds = (0.0, 1250)
    sensor.reference_temperature_thresholds = (0.0, 50.0)


while True:
    time.sleep(0.2)
    for idx, sensor in enumerate(sensors):
        # print("%d Thresholds: TC: %s , CJ: %s" %
        #   (idx, sensor.temperature_thresholds, sensor.reference_temperature_thresholds,))
        print(
            "%d: %0.1f• :> %0.1f"
            % (idx, sensor.temperature,
               sensor.reference_temperature))
        print(sensor.fault)
    print('')
    time.sleep(5)
