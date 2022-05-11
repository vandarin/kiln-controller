from enum import Enum

from microcontroller import Pin
from lib.heater import Heater
import threading
import time
from lib.zoneConfig import ZoneConfig
from lib.tempSensor import TempSensor, TempSensorReal, TempSensorSimulated
from lib.enums import BoardModel
import random
import logging

log = logging.getLogger(__name__)
event = threading.Event()


class Zone(threading.Thread):
    stats = []

    def __init__(
            self,
            name: str,
            gpio_heat: Pin,
            thermocouple: TempSensor,
            sensor_time_wait: int,
            temp_scale: str,
            gpio_active_high: bool = True,
            temperature_average_samples: int = 10,
            power_adjust: float = 1.0
    ) -> None:
        self._tuning = False
        threading.Thread.__init__(self)
        self.daemon = True
        self.zone_name = name
        self.power_adjust = power_adjust
        self.temp_sensor = TempSensorReal(
            thermocouple, sensor_time_wait, temp_scale, temperature_average_samples
        )
        self.heat = 0
        if gpio_heat is not None:
            log.info("Heater output created on %s." % (gpio_heat,))
            self.output = Heater(gpio_heat, gpio_active_high)
        else:
            self.output = None
            log.warn("No output, temp sensor only")

        self.time_step = sensor_time_wait

        self.zone_index = len(Zone.stats)
        Zone.stats.append(self.getStats())

    def __repr__(self) -> str:
        return "{Name}: {Temp}° ({Delta}) <{Heat_pct}%>".format(**self.getStats())

    def run(self):
        while True:
            # update stats
            Zone.stats[self.zone_index] = self.getStats()
            if self.output is not None:
                # heater attached, turn it on if needed
                if self._tuning:
                    self.output.on()
                    event.wait(1)
                    continue
                if self.heat > 0:
                    self.output.on()
                event.wait(self.heat)
                self.output.off()
                event.wait(self.time_step - self.heat)
            else:
                # no heater attached, just sleep
                event.wait(self.time_step)

    def getDelta(self) -> float:
        if self.output is not None:
            return self.getTemperature() - Zone.getAvgTemp()
        return 0

    @staticmethod
    def getAvgTemp() -> float:
        temps = Zone.getTemps()
        avg = sum(temps)/len(temps)
        return round(avg, 2)

    @staticmethod
    def getTemps() -> list:
        if len(Zone.stats):
            return [d['Temp'] for d in Zone.stats if d['Heated']]
        return [0]

    @staticmethod
    def getTempRange() -> float:
        temps = Zone.getTemps()
        if len(temps):
            return max(temps) - min(temps)
        return 0.0

    def getStats(self) -> dict:
        return {
            'Name': self.zone_name,
            'Heated': self.output is not None,
            'Temp': round(self.getTemperature(), 1),
            'Delta': round(self.getDelta(), 1),
            'Heat': round(self.heat, 1),
            'Heat_pct': round(self.heat / self.time_step * 100, 1),
            'Faulted': self.isFaulted(),
        }

    def isFaulted(self) -> bool:
        return self.temp_sensor.faulted

    def getFaults(self) -> dict:
        return self.temp_sensor.fault

    # return single zone temp
    def getTemperature(self) -> float:
        return self.temp_sensor.temperature

    def heat_for(self, heat_on):
        if self.output is None:
            return
        self.heat = heat_on

    def reset(self):
        self._tuning = False
        if self.output is None:
            return
        self.heat = 0
        self.output.off()

    def forceOff(self):
        self._tuning = False
        self.reset()

    def forceOn(self):
        if self._tuning and self.output is not None:
            self.output.on()

    def enableTuning(self):
        self._tuning = True


class SimulatedZone(Zone):
    def __init__(
        self,
        temp_sensor: TempSensor,
        sensor_time_wait: int,
    ) -> None:
        threading.Thread.__init__(self)
        self.heat = 0
        self.output = False
        self.temp_sensor = temp_sensor,
        self.time_step = sensor_time_wait
        self.zone_index = len(Zone.stats)
        self.zone_name = "Zone%d" % (self.zone_index,)
        Zone.stats.append(self.getStats())

    def setSimulatedParams(self, config):
        self.t_env = config.sim_t_env
        self.c_heat = config.sim_c_heat
        self.c_oven = config.sim_c_oven
        self.p_heat = config.sim_p_heat
        self.R_o_nocool = config.sim_R_o_nocool
        self.R_ho_noair = config.sim_R_ho_noair
        self.R_ho = self.R_ho_noair

        # set temps to the temp of the surrounding environment
        self.t = self.t_env  # deg C temp of oven
        self.t_h = self.t_env  # deg C temp of heating element
        self.temp_sensor.temperature = self.t_env
        # start with power at 0
        self.p_ho = 0
        self.p_env = 0
        Zone.stats[self.zone_index] = self.getStats()

    def heat_for(self, heat_on):
        self.heat = heat_on
        self.Q_h = self.p_heat * heat_on
        self.temp_changes()

    def temp_changes(self):
        # temperature change of heat element by heating
        self.t_h += self.Q_h / self.c_heat

        # energy flux heat_el -> oven
        self.p_ho = (self.t_h - self.t) / self.R_ho

        # temperature change of oven and heating element
        self.t += self.p_ho * self.time_step / self.c_oven
        self.t_h -= self.p_ho * self.time_step / self.c_heat

        # temperature change of oven by cooling to environment
        self.p_env = (self.t - self.t_env) / self.R_o_nocool
        self.t -= self.p_env * self.time_step / self.c_oven

        # introduce zone divergence - assumes zone 0 is on top
        random.seed()
        self.t -= random.randint(0, 10)/10 * (self.zone_index)

        self.temperature = self.t
        self.temp_sensor.temperature = self.t
        Zone.stats[self.zone_index] = self.getStats()
