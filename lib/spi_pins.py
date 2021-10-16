class SPI_Pins:
    def __init__(self, clock, MISO, MOSI=None) -> None:
        self.clock = clock
        self.MISO = MISO
        self.MOSI = MOSI

    def asList(self):
        return [self.clock, self.MISO, self.MOSI]

    def asDict(self):
        return {
            'clock': self.clock,
            'MISO': self.MISO,
            'MOSI': self.MOSI}
