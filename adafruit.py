#!/usr/bin/env python
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import digitalio
import lib.max31856

# Create sensor object, communicating over the board's default SPI bus
spi = board.SPI()

for i in [board.D13, board.D21, board.D27]:
    p = digitalio.DigitalInOut(i)
    p.direction = digitalio.Direction.OUTPUT
    p.value = True

# allocate a CS pin and set the direction
cs = digitalio.DigitalInOut(board.D26)
cs.direction = digitalio.Direction.OUTPUT

# create a thermocouple object with the above
thermocouple = lib.max31856.MAX31856(spi, cs)

# set the temperature thresholds for the thermocouple and cold junction
thermocouple.temperature_thresholds = (-1.5, 30.8)
thermocouple.reference_temperature_thresholds = (-1.0, 30.5)
current_faults = {}
current_cj_thresholds = (0, 0)
current_temp_thresholds = (0, 0)
print(thermocouple.reference_temperature_thresholds)
while True:
    current_temp_thresholds = thermocouple.temperature_thresholds
    current_cj_thresholds = thermocouple.reference_temperature_thresholds
    current_faults = thermocouple.fault
    print(
        "Temps:    %.2f :: cj: %.2f "
        % (thermocouple.temperature, thermocouple.reference_temperature),
        end=''
    )
    print("Thresholds:", end='')
    print("Temp low: %.2f high: %.2f | " % current_temp_thresholds, end='')
    print("CJ low:   %.2f high: %.2f" % current_cj_thresholds, end='')
    print("")
    print("Faults: ", end='')
    print(
        "Temp Hi: %s | CJ Hi: %s | "
        % (current_faults["tc_high"], current_faults["cj_high"]), end=''
    )
    print(
        "Temp Low: %s | CJ Low: %s | "
        % (current_faults["tc_low"], current_faults["cj_low"]), end=''
    )
    print(
        "Temp Range: %s | CJ Range: %s | "
        % (current_faults["tc_range"], current_faults["cj_range"]), end=''
    )
    print(
        "Open Circuit: %s | Voltage: %s "
        % (current_faults["open_tc"], current_faults["voltage"]), end=''
    )
    print("")
    print("")

    time.sleep(1.0)
