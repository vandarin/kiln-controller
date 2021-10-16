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

cs_pins = []
for chip in config.thermocouples['chips']:
    time.sleep(0.2)
    cs = digitalio.DigitalInOut(chip.cs_pin)
    cs.direction = digitalio.Direction.OUTPUT
    cs.value = True
    cs_pins.append(cs)

sensor = MAX31856(
    spi, cs_pins[0], ThermocoupleType.K, continuous=False)
sensor.temperature_thresholds = (0, 1200)
sensor.reference_temperature_thresholds = (-10, 20)

time.sleep(0.25)
current_faults = {}
current_cj_thresholds = (0, 0)
current_temp_thresholds = (0, 0)
while True:
    current_temp_thresholds = sensor.temperature_thresholds
    current_cj_thresholds = sensor.reference_temperature_thresholds
    current_faults = sensor.fault
    print(
        "Temps:    %.2f :: cj: %.2f"
        % (sensor.temperature, sensor.reference_temperature)
    )
    print("Thresholds:")
    print("Temp low: %.2f high: %.2f" % current_temp_thresholds)
    print("CJ low:   %.2f high: %.2f" % current_cj_thresholds)
    print("")
    print("Faults:")
    print(
        "Temp Hi:    %s | CJ Hi:    %s"
        % (current_faults["tc_high"], current_faults["cj_high"])
    )
    print(
        "Temp Low:   %s | CJ Low:   %s"
        % (current_faults["tc_low"], current_faults["cj_low"])
    )
    print(
        "Temp Range: %s | CJ Range: %s"
        % (current_faults["tc_range"], current_faults["cj_range"])
    )
    print("")
    print(
        "Open Circuit: %s Voltage Over/Under: %s"
        % (current_faults["open_tc"], current_faults["voltage"])
    )
    print("")

    time.sleep(5)
