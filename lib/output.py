import logging
import time

log = logging.getLogger(__name__)


class Output(object):
    def __init__(self, gpio_heat):
        self.active = False
        self.gpio_heat = gpio_heat
        self.load_libs()

    def load_libs(self):
        try:
            try:
                import RPi.GPIO as GPIO
            except ImportError:
                log.warning("Imported FakeRPi, no GPIO interaction")
                import FakeRPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.gpio_heat, GPIO.OUT)
            self.active = True
            self.GPIO = GPIO
        except:
            msg = "Could not initialize GPIOs, oven operation will only be simulated!"
            log.warning(msg)
            self.active = False

    def heat(self, sleepfor, tuning=False):
        self.GPIO.output(self.gpio_heat, self.GPIO.HIGH)
        if tuning:
            return
        time.sleep(sleepfor)
        self.off()

    def off(self):
        self.GPIO.output(self.gpio_heat, self.GPIO.LOW)
