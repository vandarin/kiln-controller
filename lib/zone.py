from enum import Enum
from lib.output import Output
import threading
import time
from lib.zoneConfig import ZoneConfig
from lib.tempSensor import TempSensorReal, TempSensorSimulated
from lib.enums import BoardModel
import random


class Zone:
    stats = []

    def __init__(
            self,
            zc: ZoneConfig,
            sensor_time_wait: int,
            temp_scale: str,
            honour_theromocouple_short_errors: bool,
            temperature_average_samples: int
    ) -> None:

        threading.Thread.__init__(self)
        self.temp_sensor = TempSensorReal(
            zc, sensor_time_wait, temp_scale,
            honour_theromocouple_short_errors,
            temperature_average_samples
        )
        self.temp_sensor.start()

        self.time_step = sensor_time_wait
        self.thermocouple_offset = zc.thermocouple_offset

        self.zone_index = len(Zone.stats)
        Zone.stats.append(self.getStats())
        self.heat = 0
        self.output = Output(zc.gpio_heat)

    def __repr__(self) -> str:
        return "{Name}: {Temp}° ({Delta}) <{Heat_pct}%>".format(**self.getStats())

    def getDelta(self) -> float:
        if len(Zone.stats):
            temps = self.getTemps()
            avg = sum(temps)/len(temps)
            return self.getTemperature() - avg
        return 0.0

    @staticmethod
    def getTemps() -> list:
        if len(Zone.stats):
            return [d['Temp'] for d in Zone.stats]
        return []

    @staticmethod
    def getTempRange() -> float:
        temps = Zone.getTemps()
        if len(temps):
            return max(temps) - min(temps)
        return 0.0

    def getStats(self) -> dict:
        return {
            'Name': "Zone_%d" % (self.zone_index + 1),
            'Temp': round(self.getTemperature(), 1),
            'Delta': round(self.getDelta(), 1),
            'Heat_pct': round(self.heat / self.time_step * 100, 0)
        }

    def getTemperature(self) -> float:
        return self.temp_sensor.temperature + self.thermocouple_offset

    def heat_for(self, heat_on):
        self.heat = heat_on
        self.output.heat(heat_on)

    def reset(self):
        self.heat = 0
        self.output.off()


class SimulatedZone(Zone):
    def __init__(
        self,
        zc: ZoneConfig,
        sensor_time_wait: int,
    ) -> None:
        threading.Thread.__init__(self)
        self.heat = 0
        self.temp_sensor = TempSensorSimulated(sensor_time_wait)
        self.thermocouple_offset = zc.thermocouple_offset
        self.time_step = sensor_time_wait
        self.zone_index = len(Zone.stats)
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
