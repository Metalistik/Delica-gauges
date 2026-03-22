#!/usr/bin/env python3

import digitalio
import board
from PIL import Image, ImageDraw
from adafruit_rgb_display import gc9a01a

# --- Display pin setup for your GC9A01 round TFT on Raspberry Pi Zero 2 W ---
cs_pin = digitalio.DigitalInOut(board.CE0)   # TFT CS -> GPIO8 / CE0 / pin 24
dc_pin = digitalio.DigitalInOut(board.D25)   # TFT DC -> GPIO25 / pin 22
reset_pin = digitalio.DigitalInOut(board.D27)  # TFT RST -> GPIO27 / pin 13

# Hardware SPI on Raspberry Pi:
spi = board.SPI()

# 240x240 round GC9A01 display
disp = gc9a01a.GC9A01A(
    spi,
    rotation=0,
    width=240,
    height=240,
    x_offset=0,
    y_offset=0,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=24000000,
)

width = disp.width
height = disp.height

# Create blank image
image = Image.new("RGB", (width, height), (0, 0, 0))
draw = ImageDraw.Draw(image)

# Background circle (yellow face)
draw.ellipse((10, 10, width - 10, height - 10), fill=(255, 220, 0), outline=(0, 0, 0), width=4)

# Eyes
draw.ellipse((65, 70, 95, 100), fill=(0, 0, 0))
draw.ellipse((145, 70, 175, 100), fill=(0, 0, 0))

# Smile
draw.arc((60, 75, 180, 185), start=20, end=160, fill=(0, 0, 0), width=8)

# Push image to display
disp.image(image)
