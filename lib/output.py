import logging
import time

from microcontroller import Pin

log = logging.getLogger(__name__)


class Output(object):
    def __init__(self, gpio_heat: Pin):
        self.active = False
        self.gpio_heat = gpio_heat
        self.load_libs()

    def load_libs(self):
        try:

            import digitalio

            GPIO = digitalio.DigitalInOut(self.gpio_heat)
            GPIO.direction = digitalio.Direction.OUTPUT
            GPIO.value = False  # default to off
            self.active = True
            self.GPIO = GPIO
        except:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            self.active = False

    def heat(self, sleepfor, tuning=False):
        self.GPIO.value = True
        if tuning:
            return
        time.sleep(sleepfor)
        self.off()

    def off(self):
        self.GPIO.value = False
