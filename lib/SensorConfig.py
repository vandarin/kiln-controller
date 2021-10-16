class SensorConfig():
    def __init__(self, cs_pin, offset, board, tc_type=None) -> None:
        self.cs_pin = cs_pin
        self.offset = offset
        self.board = board
        self.tc_type = tc_type
