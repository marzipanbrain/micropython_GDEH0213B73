import machine
import framebuf
import time
import math


class GDHE0213B73(framebuf.FrameBuffer):

    # Display resolution. Width and height are when viewed in portrait mode
    WIDTH = const(122)
    HEIGHT = const(250)

    # Screen Orientation - The value doubles as DATA_ENTRY_MODE setting
    # Portrait mode. X incr, Y incr, counter moves in X direction
    PORTRAIT = const(b"\x03")
    # Landscape mode. X incr, Y decr, counter moves in Y direction
    LANDSCAPE = const(b"\x05")

    # SSD1675B Command opcodes
    DRIVER_OUTPUT_CONTROL = const(b"\01")
    DEEP_SLEEP_MODE = const(b"\x10")
    DATA_ENTRY_MODE = const(b"\x11")
    SW_RESET = const(b"\x12")
    TEMP_SENSOR_CONTROL = const(b"\x18")
    ACTIVATE_DISPLAY_UPDATE = const(b"\x20")
    DISPLAY_UPDATE_CONTROL_2 = const(b"\x22")
    WRITE_RAM = const(b"\x24")
    BORDER_WAVEFORM_CONTROL = const(b"\x3C")
    SET_RAM_X_RANGE = const(b"\x44")
    SET_RAM_Y_RANGE = const(b"\x45")
    SET_RAM_X_ADDRESS = const(b"\x4E")
    SET_RAM_Y_ADDRESS = const(b"\x4F")

    def __init__(self, orientation=PORTRAIT):
        self._orientation = orientation
        # -------------------------------------------------------------------
        # SPI setup for communication to SSD1675B, the controller chip for GDHE0213B73
        # We can almost use the ESP32 hardware VSPI (aka SPI block 2) as is.
        # We override the MISO pin with an unused pin (0) because the default ESP32 MISO pin (19) is hard-wired to the on board LED.
        self.fakeMiso = machine.Pin(0, machine.Pin.IN)
        self.spi = machine.SPI(2, baudrate=10000000, miso=self.fakeMiso)
        # print(self.spi)
        # ChipSelect: set LOW to communicate
        self.cs = machine.Pin(5, machine.Pin.OUT, 1)
        # Data_or_Command. high = DATA , low = COMMAND
        self.dc = machine.Pin(17, machine.Pin.OUT, 0)
        # SSD1675B reset pin. Bring reset low to reset
        self.reset = machine.Pin(16, machine.Pin.OUT)
        # SSD1675B busy. HIGH means busy
        self.busy = machine.Pin(4, machine.Pin.IN)
        # Round up width to nearest byte
        bufferWidth = 8 * math.ceil(self.WIDTH / 8)
        # Set up framebuffer
        self.buffer = bytearray(bufferWidth * self.HEIGHT // 8)
        if self._orientation == self.PORTRAIT:
            super().__init__(self.buffer, self.WIDTH, self.HEIGHT, framebuf.MONO_HLSB)
        elif self._orientation == self.LANDSCAPE:
            super().__init__(self.buffer, self.HEIGHT, self.WIDTH, framebuf.MONO_VLSB)
        else:
            raise ValueError("Invalid orientation passed to contructor")

        self.hwReset()
        self.init()

    def _waitUntilIdle(self):
        """ Spin until the busy pin goes low """
        while self.busy.value() == 1:
            time.sleep_us(25)

    def _writeCommand(self, commandByte: bytes):
        """ Write a single command byte to SPI """
        # print(f'Command: hex {commandByte.hex()}')
        time.sleep_us(10)
        self.cs(0)
        self.dc(0)
        self.spi.write(commandByte[0:1])  # send 1 command byte
        self.cs(1)

    def _writeData(self, dataBytes):
        """ Write dataBytes to SPI """
        time.sleep_us(10)
        self.cs(0)
        self.dc(1)
        self.spi.write(dataBytes)
        self.cs(1)        

    def hwReset(self):
        """ Hardware reset the display. Use before initialization and to wake up display from deep sleep """
        self.reset(0)  # reset LOW to reset
        time.sleep_ms(100)
        self.reset(1)
        time.sleep_ms(100)
        self._waitUntilIdle()

    def init(self):
        """ Initialize and configure the display. Must be called after a hwReset """
        self._writeCommand(self.SW_RESET)
        self._waitUntilIdle()
        self._writeCommand(self.DRIVER_OUTPUT_CONTROL)
        self._writeData(b"\xF9\x00\x00")  # last row is xF9 = 249 == 250 rows
        self._writeCommand(self.DATA_ENTRY_MODE)
        self._writeData(self._orientation)
        # Set display X and Y address ranges
        if self._orientation == self.PORTRAIT:
            self._writeCommand(self.SET_RAM_X_RANGE)
            self._writeData(b"\x00\x0F")  # start = 0, end = 15
            self._writeCommand(self.SET_RAM_Y_RANGE)
            self._writeData(b"\x00\x00\xF9\x00")  # start = 0, End = 249
        elif self._orientation == self.LANDSCAPE:
            self._writeCommand(self.SET_RAM_X_RANGE)
            self._writeData(b"\x00\x0F")  # start = 0, end = 15
            self._writeCommand(self.SET_RAM_Y_RANGE)
            self._writeData(b"\xF9\x00\x00\x00")  # start = 249, End = 0

        self._writeCommand(self.BORDER_WAVEFORM_CONTROL)
        self._writeData(b"\x01")  # 00 = black border, 01 = white border
        self._writeCommand(self.TEMP_SENSOR_CONTROL)
        self._writeData(b"\x80")

    def show(self):
        """ Show the current buffer contents on the display """
        # Set starting RAM X and Y addresses
        if self._orientation == self.PORTRAIT:
            self._writeCommand(self.SET_RAM_X_ADDRESS)
            self._writeData(b"\x00")
            self._writeCommand(self.SET_RAM_Y_ADDRESS)
            self._writeData(b"\x00\x00")
        elif self._orientation == self.LANDSCAPE:
            self._writeCommand(self.SET_RAM_X_ADDRESS)
            self._writeData(b"\x00")
            self._writeCommand(self.SET_RAM_Y_ADDRESS)
            self._writeData(b"\xF9\x00")
        self._waitUntilIdle()
        # Write data to SSD1675B RAM
        self._writeCommand(self.WRITE_RAM)
        # This loop appears to take about 250ms, but is needed when using framebuffer.MONO_VLSB because of board expects MSB first :-(
        if self._orientation == self.LANDSCAPE:
            for i in range(len(self.buffer)):
                self.buffer[i] = self.reverseBits(self.buffer[i])
        self._writeData(self.buffer)
        # Initiate display update
        self._writeCommand(self.DISPLAY_UPDATE_CONTROL_2)
        self._writeData(b"\xF7")
        self._writeCommand(self.ACTIVATE_DISPLAY_UPDATE)
        self._waitUntilIdle()

    def deepSleep(self):
        """Put SSD1675B to deep sleep. To wake it up, call hwReset() and init()."""
        self._writeCommand(self.DEEP_SLEEP_MODE)
        self._writeData(b"\x01")

    def textWrap(self, str, x, y, color, w, h, border=None):
        """Poached from mcauser: https://forum.micropython.org/viewtopic.php?t=4434"""
        # optional box border
        if border is not None:
            self.rect(x, y, w, h, border)
        cols = w // 8
        # for each row
        j = 0
        for i in range(0, len(str), cols):
            # draw as many chars fit on the line
            self.text(str[i: i + cols], x, y + j, color)
            j += 8
            # dont overflow text outside the box
            if j >= h:
                break

    def linePath(self, x: int, y: int, points: tuple[float, ...], color: int, scale: float = 1 ):
        """ Draw a path of lines going from point to point using x,y pairs from points """
        if ((len(points) // 2) != 0 or (len(points) < 4)):
            ValueError("You must specify an even number of points")
        xStart = points[0];  # type: ignore
        yStart = points[1];  # type: ignore
        for i in range(2, len(points), 2):
            xEnd = points[i]; yEnd= points[i+1]
            self.line(int(x+xStart*scale), int(y+yStart*scale), int(x+xEnd*scale), int(y+yEnd*scale), color)
            xStart = xEnd;
            yStart = yEnd;
            # print(f'xoffset: {points[i]}, yoffset: {points[i+1]}')

    @staticmethod
    def reverseBits(b):
        """ Reverse the order of bits in a byte. Needed because framebuffer uses LSB order and the board needs MSB (in landscape mode) """
        b = (b & 0xF0) >> 4 | (b & 0x0F) << 4
        b = (b & 0xCC) >> 2 | (b & 0x33) << 2
        b = (b & 0xAA) >> 1 | (b & 0x55) << 1
        return b