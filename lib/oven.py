from lib.zone import Zone, SimulatedZone
import threading
import time
import datetime
import logging
import json

log = logging.getLogger(__name__)


class Oven(threading.Thread):
    '''parent oven class. this has all the common code
       for either a real or simulated oven'''

    def __init__(self, config):
        threading.Thread.__init__(self)
        self.daemon = True
        self.temperature = 0
        self.time_step = config.sensor_time_wait
        self.kiln_must_catch_up = config.kiln_must_catch_up
        self.kiln_must_catch_up_max_error = config.kiln_must_catch_up_max_error
        self.kwh_rate = config.kwh_rate,
        self.currency_type = config.currency_type,
        self.emergency_shutoff_temp = config.emergency_shutoff_temp
        self.initial_pid_params = {
            'ki': config.pid_ki,
            'kd': config.pid_kd,
            'kp': config.pid_kp,
            'stop_integral_windup': config.stop_integral_windup
        }
        self.zone_max_lag = config.zone_max_lag
        self.zones = []
        for zc in config.zones:
            if config.simulate:
                zone = SimulatedZone(
                    zc,
                    config.simulate,
                    config.sensor_time_wait,
                    config.temp_scale
                )
            else:
                zone = Zone(
                    zc,
                    config.simulate,
                    config.sensor_time_wait,
                    config.temp_scale
                )

            self.zones.append(zone)
        self.reset()

    def reset(self):
        self.state = "IDLE"
        self.profile = None
        self.start_time = 0
        self.runtime = 0
        self.totaltime = 0
        self.target = 0
        for zone in self.zones:
            zone.reset()
        self.pid = PID(**self.initial_pid_params)

    def run_profile(self, profile, startat=0):
        self.reset()
        for zone in self.zones:
            if zone.temp_sensor.noConnection:
                log.info(
                    "Refusing to start profile - thermocouple not connected: Zone %d" % (zone.zone_index))
                return
            if zone.temp_sensor.shortToGround:
                log.info(
                    "Refusing to start profile - thermocouple short to ground: Zone %d" % (zone.zone_index))
                return
            if zone.temp_sensor.shortToVCC:
                log.info(
                    "Refusing to start profile - thermocouple short to VCC: Zone %d" % (zone.zone_index))
                return
            if zone.temp_sensor.unknownError:
                log.info(
                    "Refusing to start profile - thermocouple unknown error: Zone %d" % (zone.zone_index))
                return

        log.info("Running schedule %s" % profile.name)
        self.profile = profile
        self.totaltime = profile.get_duration()
        self.state = "RUNNING"
        self.start_time = datetime.datetime.now()
        self.startat = startat * 60
        log.info("Starting")

    def abort_run(self):
        self.reset()

    def catch_up(self):
        '''shift the whole schedule forward in time by one time_step
        to wait for the kiln to catch up'''
        if self.kiln_must_catch_up == True:
            temp = self.getAverageTemp()
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

    def reset_if_emergency(self):
        for zone in self.zones:
            '''reset if the temperature is way TOO HOT, or other critical errors detected'''
            if (zone.temp_sensor.temperature >=
                    self.emergency_shutoff_temp):
                log.info("emergency!!! temperature too high, shutting down")
                self.reset()

            if zone.temp_sensor.noConnection:
                log.info(
                    "emergency!!! lost connection to thermocouple, shutting down")
                self.reset()

            if zone.temp_sensor.unknownError:
                log.info("emergency!!! unknown thermocouple error, shutting down")
                self.reset()

            if zone.temp_sensor.bad_percent > 30:
                log.info(
                    "emergency!!! too many errors in a short period, shutting down")
                self.reset()

    def reset_if_schedule_ended(self):
        if self.runtime > self.totaltime:
            log.info("schedule ended, shutting down")
            self.reset()

    def get_state(self):
        state = {
            'runtime': self.runtime,
            'temperature': self.getAverageTemp(),
            'target': self.target,
            'state': self.state,
            'heat': self.heat,
            'totaltime': self.totaltime,
            'kwh_rate': self.kwh_rate,
            'currency_type': self.currency_type,
            'profile': self.profile.name if self.profile else None,
            'zones': Zone.stats
        }
        return state

    def run(self):
        while True:
            if self.state == "IDLE":
                time.sleep(1)
                continue
            if self.state == "RUNNING":
                self.catch_up()
                self.update_runtime()
                self.update_target_temp()
                self.heat_then_cool()
                self.reset_if_emergency()
                self.reset_if_schedule_ended()

    def heat_then_cool(self):
        pid = self.pid.compute(self.target,
                               self.getAverageTemp())
        heat_on = float(self.time_step * pid)
        heat_off = float(self.time_step * (1 - pid))

        # self.heat is for the front end to display if the heat is on
        self.heat = 0.0
        if heat_on > 0:
            self.heat = heat_on

        for zone in self.zones:
            zone_pid = self.calc_zone_pid(pid, zone)
            zone_heat_on = float(self.time_step * zone_pid)
            zone.heat_for(zone_heat_on)
        self.log_heating(pid, heat_on, heat_off)

    def calc_zone_pid(self, pid: float, zone: Zone) -> float:
        range = zone.getTempRange()
        if pid > 0 and range > self.zone_max_lag:
            delta = zone.getDelta()
            # if delta is positive, pid decreases
            # if delta is negative, pid increases
            return clip(pid - (delta / range), 0, 1)

        # range is within tolerance, no adjustment needed
        return pid

    def getAverageTemp(self):
        temps = [d['Temp'] for d in Zone.stats]
        if len(temps) == 0:
            return 0
        return sum(temps) / len(temps)

    def log_heating(self, pid, heat_on, heat_off):
        time_left = self.totaltime - self.runtime

        log.info("BASE: temp=%.2f, target=%.2f, pid=%.3f, heat_on=%.2f, heat_off=%.2f, run_time=%d, total_time=%d, time_left=%d" %
                 (self.getAverageTemp(),
                  self.target,
                  pid,
                  heat_on,
                  heat_off,
                  self.runtime,
                  self.totaltime,
                  time_left))
        log.info("Zone info: %s" % (self.zones))


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
        time.sleep(self.time_step)

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

    def __init__(self):
        self.board = Board()
        self.output = Output()
        self.reset()

        # call parent init
        Oven.__init__(self)

        # start thread
        self.start()

    def reset(self):
        super().reset()
        self.output.cool(0)


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

        if self.ki > 0:
            if self.stop_integral_windup == True:
                if abs(self.kp * error) < window_size:
                    self.iterm += (error * timeDelta * (1/self.ki))
            else:
                self.iterm += (error * timeDelta * (1/self.ki))

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

        if out4logs > 0:
            #            log.info("pid percents pid=%0.2f p=%0.2f i=%0.2f d=%0.2f" % (out4logs,
            #                ((self.kp * error)/out4logs)*100,
            #                (self.iterm/out4logs)*100,
            #                ((self.kd * dErr)/out4logs)*100))
            log.info(
                "pid actuals pid=%0.2f p=%0.2f i=%0.2f d=%0.2f"
                % (
                    out4logs,
                    self.kp * error,
                    self.iterm,
                    self.kd * dErr
                )
            )

        return output


def clip(value, lower, upper):
    return lower if value < lower else upper if value > upper else value
