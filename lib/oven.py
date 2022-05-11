import os
from lib.max31856 import MAX31856, SampleType
from lib.safetyswitch import SafetySwitch
from lib.tempSensor import TempSensorSimulated
from lib.zone import Zone, SimulatedZone
import board
import csv
import digitalio
import threading
import time
import datetime
import logging
import json

log = logging.getLogger(__name__)
event = threading.Event()
script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
runlog_path = os.path.join(script_dir, "storage", "runlog")


class Oven(threading.Thread):
    '''parent oven class. this has all the common code
       for either a real or simulated oven'''

    def __init__(self, config):
        self._tuning = False
        self.runID = None
        threading.Thread.__init__(self)
        self.daemon = True
        self.temperature = 0
        self.faulted_count = 0
        self.time_step = config.sensor_time_wait
        self.kiln_must_catch_up = config.kiln_must_catch_up
        self.kiln_must_catch_up_max_error = config.kiln_must_catch_up_max_error
        self.emergency_shutoff_temp = config.emergency_shutoff_temp
        self.initial_pid_params = {
            'ki': config.pid_ki,
            'kd': config.pid_kd,
            'kp': config.pid_kp,
            'stop_integral_windup': config.stop_integral_windup
        }
        self.zone_max_lag = config.zone_max_lag
        self.zones = []
        if config.simulate:
            for zc in config.zones:
                self.zones.append(
                    SimulatedZone(
                        TempSensorSimulated(config.sensor_time_wait),
                        config.sensor_time_wait,
                    )
                )
        else:
            spi = board.SPI()
            sensors = []
            for chip in config.thermocouples['chips']:
                cs = digitalio.DigitalInOut(chip.cs_pin)
                cs.direction = digitalio.Direction.OUTPUT
                cs.value = True
                sensor = MAX31856(
                    spi, cs, chip.tc_type, continuous=True, ac_freq_50hz=config.thermocouples['ac_freq_50hz'],
                    samples=SampleType.AVG_SEL_4SAMP
                )
                sensors.append(sensor)
            for sensor in sensors:
                # hardcoded safety limits in celsius
                sensor.temperature_thresholds = (-20.0, 1250)
                sensor.reference_temperature_thresholds = (-20.0, 60.0)
            for zc in config.zones:
                zone = Zone(
                    name=zc.name,
                    gpio_heat=zc.gpio_heat,
                    gpio_active_high=zc.gpio_active_high,
                    thermocouple=sensors[zc.thermocouple],
                    sensor_time_wait=config.sensor_time_wait,
                    temp_scale=config.temp_scale,
                    temperature_average_samples=config.temperature_average_samples
                )
                zone.start()
                self.zones.append(zone)
            self.safety_switch = SafetySwitch(
                config.safety_switch, config.safety_switch_active_value)
        self.hooks = Hooks(config.hook_run_profile, config.hook_reset)
        self.reset()

    def reset(self):
        self._tuning = False
        self.state = "IDLE"
        self.profile = None
        self.runID = None
        self.start_time = 0
        self.runtime = 0
        self.totaltime = 0
        self.target = 0
        self.faulted_count = 0
        for zone in self.zones:
            zone.reset()
        self.pid = PID(**self.initial_pid_params)
        self.safety_switch.off()
        if self.hooks.reset:
            os.system(self.hooks.reset)

    def run_profile(self, profile, startat=0):
        self.reset()
        zone: Zone
        for zone in self.zones:
            if zone.getTemperature() > self.emergency_shutoff_temp:
                log.error("Refusing to start profile - Zone %s is too hot. %0.1f" %
                          (zone.name, zone.getTemperature()))
            if zone.isFaulted():
                log.error(
                    "Refusing to start profile - Zone %s thermocouple faulted. \n%s" % (zone.name, zone.getFaults()))
                return

        log.info("Running schedule %s" % profile.name)
        self.profile = profile
        self.totaltime = profile.get_duration()
        self.state = "RUNNING"
        self.start_time = datetime.datetime.now()
        self.startat = startat * 60
        self.safety_switch.on()
        self.runID = "%s-%s" % (
            self.start_time.strftime('%Y%m%d-%H%M'),
            profile.name
        )
        self.write_to_runlog(headers=True)
        log.info("Starting %s" % (profile,))
        if self.hooks.run_profile:
            os.system(self.hooks.run_profile)

    def abort_run(self):
        self.reset()

    def catch_up(self):
        '''shift the whole schedule forward in time by one time_step
        to wait for the kiln to catch up'''
        if self.kiln_must_catch_up == True:
            temp = Zone.getAvgTemp()
            # kiln too cold, wait for it to heat up
            if self.target - temp > self.kiln_must_catch_up_max_error and self.profile.isRampingUp(self.runtime):
                log.info("kiln must catch up, too cold, shifting schedule")
                self.start_time = self.start_time + \
                    datetime.timedelta(seconds=self.time_step)
            # kiln too hot, wait for it to cool down
            if temp - self.target > self.kiln_must_catch_up_max_error and not self.profile.isRampingUp(self.runtime):
                log.info("kiln must catch up, too hot, shifting schedule")
                self.start_time = self.start_time + \
                    datetime.timedelta(seconds=self.time_step)

    def update_runtime(self):
        runtime_delta = datetime.datetime.now() - self.start_time
        if runtime_delta.total_seconds() < 0:
            runtime_delta = datetime.timedelta(0)

        if self.startat > 0:
            self.runtime = self.startat + runtime_delta.total_seconds()
        else:
            self.runtime = runtime_delta.total_seconds()

    def update_target_temp(self):
        self.target = self.profile.get_target_temperature(self.runtime)

    def update_temperature(self):
        self.temperature = Zone.getAvgTemp()

    def reset_if_emergency(self):
        zone: Zone
        for zone in self.zones:
            '''reset if the temperature is way TOO HOT, or other critical errors detected'''
            if (zone.getTemperature() >=
                    self.emergency_shutoff_temp):
                log.error("emergency!!! temperature too high, shutting down")
                self.reset()

            if zone.isFaulted():
                self.faulted_count += 1

            if zone.temp_sensor.bad_percent > 30:
                log.error(
                    "emergency!!! too many errors in a short period, shutting down")
                self.reset()
        if self.faulted_count > 10:
            log.error(
                "emergency!! Too many thermocouple faults. shutting down."
            )
            self.reset()

    def reset_if_schedule_ended(self):
        if self.runtime > self.totaltime:
            log.info("schedule ended, shutting down")
            self.reset()

    def get_state(self):
        state = {
            'runtime': self.runtime,
            'temperature': Zone.getAvgTemp(),
            'target': round(self.target, 2),
            'state': self.state,
            'totaltime': self.totaltime,
            'profile': self.profile.name if self.profile else None,
            'zones': Zone.stats.copy()
        }
        return state

    def run(self):
        while True:
            self.update_temperature()
            if self._tuning:
                self.reset_if_emergency()
                continue
            if self.state == "IDLE":
                event.wait(1)
                continue
            if self.state == "RUNNING":
                self.catch_up()
                self.update_runtime()
                self.update_target_temp()
                self.heat_then_cool()
                self.reset_if_emergency()
                self.reset_if_schedule_ended()
                self.write_to_runlog()
                event.wait(self.time_step)

    def heat_then_cool(self):
        pid = self.pid.compute(self.target,
                               Zone.getAvgTemp())
        heat_on = float(self.time_step * pid)

        zone: Zone
        for zone in self.zones:
            zone_pid = clip(self.calc_zone_pid(pid, zone), 0, 1)
            zone_heat_on = float(self.time_step * zone_pid)
            zone.heat_for(zone_heat_on)
        self.log_heating(pid, heat_on, self.time_step - heat_on)

    def calc_zone_pid(self, pid: float, zone: Zone) -> float:
        zone_error = zone.getTemperature() - self.target
        if pid <= 0:
            if zone_error < 0 - self.zone_max_lag:
                # zone is lagging and others are off, force power on
                return 0.15
            return 0

        if zone_error > self.zone_max_lag:
            # above the setpoint, decrease power on time
            return pid * 0.8
        if zone.getTemperature() > self.target and zone.getTempRange() > self.zone_max_lag * 2:
            # above the setpoint and another zone is lagging, decrease power on time
            return pid * 0.9
        if zone.getTemperature() > self.temperature and zone.getTempRange() > self.zone_max_lag:
            # above the average and another zone is lagging, decrease power on time
            return pid * 0.95
        if zone_error < 0 - self.zone_max_lag:
            # zone is lagging, increase power on time
            return pid * 2.5
        # all zones within allowed variance, follow PID loop
        return pid * zone.power_adjust

    def log_heating(self, pid, heat_on, heat_off):
        time_left = self.totaltime - self.runtime

        log.info("BASE: temp=%.2f, target=%.2f, pid=%.3f, heat_on=%.2f, heat_off=%.2f, run_time=%d, total_time=%d, time_left=%d" %
                 (Zone.getAvgTemp(),
                  self.target,
                  pid,
                  heat_on,
                  heat_off,
                  self.runtime,
                  self.totaltime,
                  time_left))
        log.info("Zone info: %s" % (self.zones))

    def write_to_runlog(self, headers=False):
        if self.runID is None:
            return
        filename = '%s.csv' % (self.runID,)
        with open(os.path.join(runlog_path, filename), 'a', newline='') as csvfile:
            runwriter = csv.writer(csvfile)
            if headers:
                header_row = ['Time', 'Target', 'AVG', 'PID']

                for zone in Zone.stats:
                    header_row.append(zone['Name'])
                    header_row.append('%s err' % (zone['Name'],))
                    header_row.append('%s pow' % (zone['Name'],))
                runwriter.writerow(header_row)

            row_data = [
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                round(self.target, 1),
                round(self.temperature, 1),
                round(self.pid.lastValue, 2)
            ]
            for zone in Zone.stats:
                row_data.append(zone['Temp'])
                row_data.append(zone['Delta'])
                row_data.append(zone['Heat_pct'])
            runwriter.writerow(row_data)

    def forceOff(self):
        self.safety_switch.off()
        self._tuning = False
        for zone in self.zones:
            zone.forceOff()

    def forceOn(self):
        if self._tuning:
            self.safety_switch.on()
            zone: Zone
            for zone in self.zones:
                zone.enableTuning()
                zone.forceOn()

    def enableTuning(self):
        self._tuning = True
        for zone in self.zones:
            zone.enableTuning()


class SimulatedOven(Oven):

    def __init__(self, config):
        # call parent init
        Oven.__init__(self, config)

        for zone in self.zones:
            zone.setSimulatedParams(config)

        self.reset()

        # start thread
        self.start()
        log.info("SimulatedOven started")

    def heat_then_cool(self):
        super().heat_then_cool()
        # we don't actually spend time heating & cooling during
        # a simulation, so sleep.
        event.wait(self.time_step)

    def log_heating(self, pid, heat_on, heat_off):
        super().log_heating(pid, heat_on, heat_off)
        for idx, zone in enumerate(self.zones):
            log.info(
                "Zone %d simulation: -> %dW heater: %.0f -> %dW oven: %.0f -> %dW env" %
                (
                    idx,
                    int(zone.p_heat * pid),
                    zone.t_h,
                    int(zone.p_ho),
                    zone.t,
                    int(zone.p_env)
                )
            )


class RealOven(Oven):

    def __init__(self, config):
        # call parent init
        Oven.__init__(self, config)
        self.reset()

        # start thread
        self.start()


class Profile():
    def __init__(self, json_data):
        obj = json.loads(json_data)
        self.name = obj["name"]
        self.data = sorted(obj["data"])

    def get_duration(self):
        return max([t for (t, x) in self.data])

    def get_surrounding_points(self, time):
        if time > self.get_duration():
            return (None, None)

        prev_point = None
        next_point = None

        for i in range(len(self.data)):
            if time < self.data[i][0]:
                prev_point = self.data[i-1]
                next_point = self.data[i]
                break

        return (prev_point, next_point)

    def get_target_temperature(self, time):
        if time > self.get_duration():
            return 0

        (prev_point, next_point) = self.get_surrounding_points(time)

        incl = float(next_point[1] - prev_point[1]) / \
            float(next_point[0] - prev_point[0])
        temp = prev_point[1] + (time - prev_point[0]) * incl
        return temp

    def isRampingUp(self, time):
        (prev_point, next_point) = self.get_surrounding_points(time)
        incl = float(next_point[1] - prev_point[1]) / \
            float(next_point[0] - prev_point[0])
        return (incl > 0)


class PID():

    def __init__(self, ki=1, kp=1, kd=1, stop_integral_windup=True):
        self.ki = ki
        self.kp = kp
        self.kd = kd
        self.stop_integral_windup = stop_integral_windup
        self.lastNow = datetime.datetime.now()
        self.iterm = 0
        self.lastErr = 0
        self.lastValue = 0

    # FIX - this was using a really small window where the PID control
    # takes effect from -1 to 1. I changed this to various numbers and
    # settled on -50 to 50 and then divide by 50 at the end. This results
    # in a larger PID control window and much more accurate control...
    # instead of what used to be binary on/off control.
    def compute(self, setpoint, ispoint):
        now = datetime.datetime.now()
        timeDelta = (now - self.lastNow).total_seconds()

        window_size = 100

        error = float(setpoint - ispoint)

        dErr = (error - self.lastErr) / timeDelta
        output = self.kp * error + self.iterm + self.kd * dErr
        out4logs = output
        output = sorted([-1 * window_size, output, window_size])[1]
        self.lastErr = error
        self.lastNow = now

        # not actively cooling, so
        if output < 0:
            output = 0

        output = float(output / window_size)

        if self.ki > 0 and out4logs < 120:
            # TODO: should the out4logs test be < 100 ??
            if self.stop_integral_windup == True:
                if abs(self.kp * error) < window_size:
                    self.iterm += (error * timeDelta * (1/self.ki))
            else:
                self.iterm += (error * timeDelta * (1/self.ki))

        log.info(
            "pid actuals pid=%0.2f p=%0.2f i=%0.2f d=%0.2f"
            % (
                out4logs,
                self.kp * error,
                self.iterm,
                self.kd * dErr
            )
        )
        self.lastValue = output
        return output


class Hooks():
    def __init__(self, run_profile, reset) -> None:
        self.run_profile = run_profile
        self.reset = reset


def clip(value, lower, upper):
    return lower if value < lower else upper if value > upper else value
