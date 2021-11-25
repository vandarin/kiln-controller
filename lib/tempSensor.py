from lib.max31856 import MAX31856
from lib.zoneConfig import ZoneConfig
from lib.enums import BoardModel
import threading
import time
import logging

log = logging.getLogger(__name__)


class TempSensor(threading.Thread):
    def __init__(self, sensor_time_wait: int):
        threading.Thread.__init__(self)
        self.daemon = True
        self.temperature = 0
        self.bad_percent = 0
        self.time_step = sensor_time_wait
        self.faulted = False
        self.start()


class TempSensorSimulated(TempSensor):
    '''not much here, just need to be able to set the temperature'''

    def __init__(self, sensor_time_wait):
        TempSensor.__init__(self, sensor_time_wait)


class TempSensorReal(TempSensor):
    '''real temperature sensor thread that takes N measurements
       during the time_step'''

    def __init__(
            self,
            thermocouple: MAX31856,
            sensor_time_wait: int,
            temp_scale: str,
            temperature_average_samples: int = 1,
            offset: float = 0.0,
    ):
        self.temp_scale = temp_scale
        self.temperature_average_samples = temperature_average_samples
        self.sleeptime = sensor_time_wait / float(temperature_average_samples)
        self.bad_count = 0
        self.ok_count = 0
        self.bad_stamp = 0
        self.thermocouple = thermocouple
        self.offset = offset
        TempSensor.__init__(self, sensor_time_wait)

    def convert_to_scale(self, value):
        if self.temp_scale.lower() == 'f':
            return (value * 9/5) + 32
        return value

    def run(self):
        '''use a moving average of config.temperature_average_samples across the time_step'''
        temps = []
        while True:
            # reset error counter if time is up
            if (time.time() - self.bad_stamp) > (self.time_step * 2):
                if self.bad_count + self.ok_count:
                    self.bad_percent = (
                        self.bad_count / (self.bad_count + self.ok_count)) * 100
                else:
                    self.bad_percent = 0
                self.bad_count = 0
                self.ok_count = 0
                self.bad_stamp = time.time()

            temp = self.thermocouple.temperature
            self.faulted = self.thermocouple.fault['raw']

            if not self.faulted:
                temps.append(temp)
                if len(temps) > self.temperature_average_samples:
                    del temps[0]
                self.ok_count += 1
            else:
                log.error("Problem reading temp. Faults: %s" %
                          (self.thermocouple.fault,))
                self.bad_count += 1

            if len(temps):
                self.temperature = self.convert_to_scale(
                    sum(temps) / len(temps)) + self.offset
            log.debug("Logged temp: %0.1f" % (self.temperature,))
            time.sleep(self.sleeptime)
