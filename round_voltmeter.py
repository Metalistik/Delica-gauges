#!/usr/bin/env python3

import time
import digitalio
import board
from PIL import Image
from adafruit_rgb_display import gc9a01a

print("STARTING...")

# --- SPI setup ---
spi = board.SPI()
while not spi.try_lock():
    pass
spi.configure(baudrate=12000000, phase=0, polarity=0)
spi.unlock()

# --- Pins ---
cs = digitalio.DigitalInOut(board.CE0)   # pin 24
dc = digitalio.DigitalInOut(board.D25)   # pin 22
rst = digitalio.DigitalInOut(board.D27)  # pin 13

print("INIT DISPLAY...")

# --- Display init ---
disp = gc9a01a.GC9A01A(
    spi,
    cs=cs,
    dc=dc,
    rst=rst,
    width=240,
    height=240,
    rotation=90,
    baudrate=12000000
)

print("DRAWING...")

# --- Draw solid red screen ---
image = Image.new("RGB", (240, 240), (255, 0, 0))
disp.image(image)

print("DONE - HOLDING SCREEN")

# Keep program running
while True:
    time.sleep(1)
