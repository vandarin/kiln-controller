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
        self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False


class TempSensorSimulated(TempSensor):
    '''not much here, just need to be able to set the temperature'''

    def __init__(self, sensor_time_wait):
        TempSensor.__init__(self, sensor_time_wait)


class TempSensorReal(TempSensor):
    '''real temperature sensor thread that takes N measurements
       during the time_step'''

    def __init__(self, zc: ZoneConfig, sensor_time_wait: int, temp_scale: str, honour_theromocouple_short_errors: bool):
        TempSensor.__init__(self, sensor_time_wait)
        self.sleeptime = self.time_step / \
            float(zc.temperature_average_samples)
        self.bad_count = 0
        self.ok_count = 0
        self.bad_stamp = 0
        self.honour_theromocouple_short_errors = honour_theromocouple_short_errors
        self.temperature_average_samples = zc.temperature_average_samples

        if zc.board is BoardModel.MAX31855:
            log.info("init MAX31855")
            from lib.max31855 import MAX31855, MAX31855Error
            self.thermocouple = MAX31855(zc.pins.cs,
                                         zc.pins.clock,
                                         zc.pins.data,
                                         temp_scale)

        elif zc.board is BoardModel.MAX31856:
            log.info("init MAX31856")
            from lib.max31856 import MAX31856

            self.thermocouple = MAX31856(tc_type=zc.MAX31856_type,
                                         software_spi=zc.pins.asDict(),
                                         units=temp_scale,
                                         ac_freq_50hz=zc.ac_freq_50hz,
                                         )
        else:
            raise NotImplementedError("Unknown Board Type")

def __repr__(self) -> str:
    return "T: %0.2f%s" % (self.temp)

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

            temp = self.thermocouple.get()
            self.noConnection = self.thermocouple.noConnection
            self.shortToGround = self.thermocouple.shortToGround
            self.shortToVCC = self.thermocouple.shortToVCC
            self.unknownError = self.thermocouple.unknownError

            is_bad_value = self.noConnection | self.unknownError
            if self.honour_theromocouple_short_errors:
                is_bad_value |= self.shortToGround | self.shortToVCC

            if not is_bad_value:
                temps.append(temp)
                if len(temps) > self.temperature_average_samples:
                    del temps[0]
                self.ok_count += 1

            else:
                log.error("Problem reading temp N/C:%s GND:%s VCC:%s ???:%s" %
                          (self.noConnection, self.shortToGround, self.shortToVCC, self.unknownError))
                self.bad_count += 1

            if len(temps):
                self.temperature = sum(temps) / len(temps)
            time.sleep(self.sleeptime)
