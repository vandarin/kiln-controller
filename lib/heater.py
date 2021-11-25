import logging
import time

from microcontroller import Pin

log = logging.getLogger(__name__)


class Heater(object):
    def __init__(self, gpio_heat: Pin, active_value: bool = True):
        self.loaded = False
        self._active_value = active_value
        self.gpio_heat = gpio_heat
        self.load_libs()

    def load_libs(self):
        try:

            import digitalio

            GPIO = digitalio.DigitalInOut(self.gpio_heat)
            GPIO.direction = digitalio.Direction.OUTPUT
            GPIO.value = not self._active_value  # default to off
            self.loaded = True
            self.GPIO = GPIO
        except:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            self.loaded = False

    def on(self):
        if self.loaded:
            self.GPIO.value = self._active_value

    def off(self):
        if self.loaded:
            self.GPIO.value = not self._active_value
