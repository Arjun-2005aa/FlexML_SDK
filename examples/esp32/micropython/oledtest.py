from machine import Pin, I2C
import time

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
print("I2C scan:", i2c.scan())  # should show [60] for 0x3C

# Try SH1106 (common on HW-239)
try:
    import sh1106
    oled = sh1106.SH1106_I2C(128, 64, i2c, addr=0x3C)
    oled.fill(0)
    oled.text("HW-239 / SH1106", 0, 0)
    oled.text("I2C 0x3C OK",     0, 16)
    oled.text("MicroPython",     0, 32)
    oled.show()
    print("Using SH1106 driver")
except Exception as e:
    print("SH1106 init failed:", e)
    try:
        import ssd1306
        oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.text("SSD1306 fallback", 0, 0)
        oled.show()
        print("Using SSD1306 driver")
    except Exception as e2:
        print("SSD1306 init failed too:", e2)
