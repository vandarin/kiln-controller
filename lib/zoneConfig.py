from lib.enums import BoardModel
from lib.spi_pins import SPI_Pins


class ZoneConfig:
    heater_pins = []
    spi_pins = []

    def __init__(
        self,
        gpio_heat: int,
        thermocouple_offset: int,
        board: BoardModel,
        pins: SPI_Pins,
        MAX31856_type=None,
        temperature_average_samples=10,
        ac_freq_50hz=False
    ) -> None:
        # Each zone must control its own heater
        if gpio_heat in self.heater_pins + self.spi_pins:
            raise PinConflict(gpio_heat)
        self.heater_pins.append(gpio_heat)

        # CS pin must be unique, the others can be shared
        if pins.cs in self.heater_pins + self.spi_pins:
            raise PinConflict(pins.cs)
        self.spi_pins.extend(pins.asList())

        self.gpio_heat = gpio_heat
        self.thermocouple_offset = thermocouple_offset
        self.board = board
        self.pins = pins
        self.MAX31856_type = MAX31856_type
        self.temperature_average_samples = temperature_average_samples
        self.ac_freq_50hz = ac_freq_50hz


class PinConflict(Exception):
    def __init__(self, pin):
        self.pin = pin
        self.message = "Pin %i has already been used." % (pin)
        super().__init__(self.message)
