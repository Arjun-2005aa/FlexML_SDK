# sh1106.py — minimal MicroPython SH1106 I2C driver (128x64)
# Works with many HW-239 modules (I2C addr 0x3C/0x3D)

from micropython import const
import framebuf

SET_CONTRAST        = const(0x81)
SET_DISP            = const(0xAE)
SET_DISP_ON         = const(0xAF)
SET_NORM_INV        = const(0xA6)
SET_DISP_OFFSET     = const(0xD3)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP       = const(0xA0)
SET_MUX_RATIO       = const(0xA8)
SET_COM_OUT_DIR     = const(0xC0)
SET_DISP_CLK_DIV    = const(0xD5)
SET_PRECHARGE       = const(0xD9)
SET_VCOM_DESEL      = const(0xDB)
SET_CHARGE_PUMP     = const(0x8D)

# SH1106 page/column commands
SET_PAGE_ADDR       = const(0xB0)   # 0xB0..0xB7
SET_COL_LOW         = const(0x00)   # lower 4 bits of column
SET_COL_HIGH        = const(0x10)   # upper 4 bits of column
SET_ADDR_MODE       = const(0x20)   # not fully used by SH1106

class SH1106(framebuf.FrameBuffer):
    # SH1106 has 132 columns x 64 rows RAM; most 128x64 panels have a 2-pixel left offset.
    def __init__(self, width, height, external_vcc=False, rotate=0):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.rotate = rotate
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()
        self.fill(0)
        self.show()

    def init_display(self):
        for cmd in (
            SET_DISP,                   # display off
            SET_DISP_CLK_DIV, 0x80,
            SET_MUX_RATIO, self.height - 1,
            SET_DISP_OFFSET, 0x00,
            SET_DISP_START_LINE | 0x00,
            SET_CHARGE_PUMP, 0x14 if not self.external_vcc else 0x10,
            SET_NORM_INV,               # normal display
            SET_SEG_REMAP | 0x01,       # column addr 127 -> SEG0
            SET_COM_OUT_DIR | 0x08,     # scan from COM[N] to COM0
            SET_CONTRAST, 0xCF,
            SET_PRECHARGE, 0xF1 if not self.external_vcc else 0x22,
            SET_VCOM_DESEL, 0x30,
            SET_DISP_ON                 # display on
        ):
            self.write_cmd(cmd)

    # --- to be provided by subclass (I2C/SPI) ---
    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP_ON)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast & 0xFF)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        # SH1106 needs explicit page writes with a column offset.
        # Most 128x64 panels are mapped starting at column 2.
        col_offset = 2
        for page in range(self.pages):
            self.write_cmd(SET_PAGE_ADDR | page)
            self.write_cmd(SET_COL_LOW  | ((col_offset + 0) & 0x0F))
            self.write_cmd(SET_COL_HIGH | (((col_offset + 0) >> 4) & 0x0F))
            # Data prefix 0x40 for I2C writes
            self.write_data(self.buffer[page * self.width:(page + 1) * self.width])

class SH1106_I2C(SH1106):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False, rotate=0):
        self.i2c = i2c
        self.addr = addr
        self.tmp = bytearray(2)
        self._bufprefix = bytearray(1)  # 0x40
        super().__init__(width, height, external_vcc, rotate)

    def write_cmd(self, cmd):
        self.tmp[0] = 0x80  # Co=1, D/C#=0
        self.tmp[1] = cmd & 0xFF
        self.i2c.writeto(self.addr, self.tmp)

    def write_data(self, buf):
        # writevto: [data_prefix, payload]
        self._bufprefix[0] = 0x40
        self.i2c.writevto(self.addr, (self._bufprefix, buf))
