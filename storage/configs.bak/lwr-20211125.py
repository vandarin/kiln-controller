import logging
from lib.SensorConfig import SensorConfig
from lib.max31856 import ThermocoupleType
from lib.zone import ZoneConfig, BoardModel
import board
########################################################################
#
#   General options

# Logging
log_level = logging.INFO
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# Server
listening_ip = "0.0.0.0"
listening_port = 8081

# Cost Estimate
kwh_rate = 0.112085  # Rate in currency_type to calculate cost to run job
currency_type = "$"   # Currency Symbol to show when calculating cost to run job

########################################################################
#
#   GPIO Setup (BCM SoC Numbering Schema)
#

# Pin to control safety contactor. Should be wired to cut power to all heater circuits.
safety_switch = board.D4
# Set true for active high, false for active low
safety_switch_active_value = True

thermocouples = {
    # Assumes using hardware SPI0
    'chips': [
        SensorConfig(
            cs_pin=board.D26,
            # If you put your thermocouple in ice water and it reads 36F, you can
            # set set this offset to -4 to compensate.  This probably means you have a
            # cheap thermocouple.  Invest in a better thermocouple.
            offset=0,
            # see lib/max31856.py for other thermocouple_type, only applies to max31856
            tc_type=ThermocoupleType.K),
        SensorConfig(
            cs_pin=board.D13,
            offset=0,
            tc_type=ThermocoupleType.K),
        SensorConfig(
            cs_pin=board.D21,
            offset=0,
            tc_type=ThermocoupleType.K),
        SensorConfig(
            cs_pin=board.D27,
            offset=0,
            tc_type=ThermocoupleType.K),

    ],
    # Thermocouple AC frequency filtering - set to True if in a 50Hz locale, else leave at False for 60Hz locale
    'ac_freq_50hz': False
}

zones = (
    ZoneConfig(
        # Top Ring
        name="Top",
        # Output pin
        gpio_heat=board.D23,
        gpio_active_high=False,
        # thermocouple reference, zero-indexed
        thermocouple=0,
    ),
    ZoneConfig(
        # Middle Ring
        name="Mid",
        # Output
        gpio_heat=board.D22,
        gpio_active_high=False,
        thermocouple=1,
    ),
    ZoneConfig(
        # Bottom Ring
        name="Bot",
        # Output
        gpio_heat=board.D12,
        gpio_active_high=False,
        thermocouple=2,
    ),
    ZoneConfig(
        # Enclosure, Temp only
        name="E",
        gpio_heat=None,
        thermocouple=3,
    ),
)

########################################################################
#
# max differential between zones.
#
# If a zone falls behind by more than this many degrees, power will be redistributed until the zones equalize.
zone_max_lag = 5


########################################################################
#
# duty cycle of the entire system in seconds
#
# Every N seconds a decision is made about switching the relay[s]
# on & off and for how long. The thermocouple is read
# temperature_average_samples times during and the average value is used.
sensor_time_wait = 2


########################################################################
#
#   PID parameters
#
# These parameters control kiln temperature change. These settings work
# well with the simulated oven. You must tune them to work well with
# your specific kiln. Note that the integral pid_ki is
# inverted so that a smaller number means more integral action.
pid_kp = 9.570142772019617
pid_ki = 19.217244222600907
pid_kd = 440.01547623017103


########################################################################
#
# Initial heating and Integral Windup
#
# During initial heating, if the temperature is constantly under the
# setpoint,large amounts of Integral can accumulate. This accumulation
# causes the kiln to run above the setpoint for potentially a long
# period of time. These settings allow integral accumulation only when
# the temperature is close to the setpoint. This applies only to the integral.
stop_integral_windup = True

########################################################################
#
#   Simulation parameters
simulate = False
sim_t_env = 60.0   # deg C
sim_c_heat = 100.0  # J/K  heat capacity of heat element
sim_c_oven = 5000.0  # J/K  heat capacity of oven
sim_p_heat = 5450.0  # W    heating power of oven
sim_R_o_nocool = 1.0    # K/W  thermal resistance oven -> environment
sim_R_o_cool = 0.05   # K/W  " with cooling
sim_R_ho_noair = 0.1    # K/W  thermal resistance heat element -> oven
sim_R_ho_air = 0.05   # K/W  " with internal air circulation


########################################################################
#
#   Time and Temperature parameters
#
# If you change the temp_scale, all settings in this file are assumed to
# be in that scale.

temp_scale = "f"  # c = Celsius | f = Fahrenheit - Unit to display
# s = Seconds | m = Minutes | h = Hours - Slope displayed in temp_scale per time_scale_slope
time_scale_slope = "h"
# s = Seconds | m = Minutes | h = Hours - Enter and view target time in time_scale_profile
time_scale_profile = "m"

# emergency shutoff the profile if this temp is reached or exceeded.
# This just shuts off the profile. If your SSR is working, your kiln will
# naturally cool off. If your SSR has failed/shorted/closed circuit, this
# means your kiln receives full power until your house burns down.
# this should not replace you watching your kiln or use of a kiln-sitter
emergency_shutoff_temp = 2264  # cone 7

# If the kiln cannot heat or cool fast enough and is off by more than
# kiln_must_catch_up_max_error  the entire schedule is shifted until
# the desired temperature is reached. If your kiln cannot attain the
# wanted temperature, the schedule will run forever. This is often used
# for heating as fast as possible in a section of a kiln schedule/profile.
kiln_must_catch_up = True
kiln_must_catch_up_max_error = 10  # degrees
