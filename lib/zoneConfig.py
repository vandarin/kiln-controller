from microcontroller import Pin
from lib.max31856 import MAX31856


class ZoneConfig:

    def __init__(
        self,
        name: str,
        gpio_heat: Pin,
        thermocouple: MAX31856,
        gpio_active_high: bool = True,
        power_adjust: float = 1.0,
    ) -> None:
        self.name = name
        self.gpio_heat = gpio_heat
        self.gpio_active_high = gpio_active_high
        self.thermocouple = thermocouple
        self.power_adjust = power_adjust
