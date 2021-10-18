from microcontroller import Pin
from lib.max31856 import MAX31856


class ZoneConfig:

    def __init__(
        self,
        name: str,
        gpio_heat: Pin,
        thermocouple: MAX31856
    ) -> None:
        self.name = name
        self.gpio_heat = gpio_heat
        self.thermocouple = thermocouple
