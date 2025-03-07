"""Generic 240x240 GC9A01

Generic display connected to a Raspberry Pi Pico.

"""
# hardware config
SCL_PIN = 14 #chip pin 19 
SDA_PIN = 15 #chip pin 20
DC_PIN = 4   #chip pin 6
CS_PIN = 5   #chip pin 7 
RST_PIN = 6  #chip pin 9 
BACK_PIN = 10 #chip pin 12

from machine import Pin, SPI
import gc9a01

TFA = 0
BFA = 0
WIDE = 0
TALL = 1

SCREEN_SIZE = (240, 240)

def rgb_to_rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def config(rotation=1, buffer_size=0, options=0):
    """Configure the display and return an instance of gc9a01.GC9A01."""

    spi = SPI(1, baudrate=30000000, sck=Pin(SCL_PIN), mosi=Pin(SDA_PIN), polarity=0, phase=0)
    return gc9a01.GC9A01(
        spi,
        240,
        240,
        reset=Pin(RST_PIN, Pin.OUT),
        cs=Pin(CS_PIN, Pin.OUT),
        dc=Pin(DC_PIN, Pin.OUT),
        backlight=Pin(10, Pin.OUT),
        rotation=rotation,
        options=options,
        buffer_size=buffer_size,
    )