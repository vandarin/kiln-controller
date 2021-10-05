class SPI_Pins:
    def __init__(self, cs, clock, data, di=None) -> None:
        self.cs = cs
        self.clock = clock
        self.data = data
        self.di = di

    def asList(self):
        return [self.cs, self.clock, self.data, self.di]

    def asDict(self):
        return {'cs': self.cs,
                'clk': self.clock,
                'do': self.data,
                'di': self.di}
