#!/usr/bin/env python3

import time
from math import cos, sin, radians
from PIL import Image, ImageDraw, ImageFont

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import gc9a01

# --------------------------
# DISPLAY SETUP
# --------------------------
serial = spi(
    port=0,
    device=0,
    gpio_DC=25,
    gpio_RST=24,
    bus_speed_hz=40000000
)

device = gc9a01(serial, width=240, height=240, rotate=0)

# --------------------------
# FONT
# --------------------------
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
except:
    font = ImageFont.load_default()

# --------------------------
# VOLTMETER DRAW
# --------------------------
def draw_voltmeter(draw, voltage):
    cx, cy = 120, 120
    radius = 100

    # draw circle
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline="white"
    )

    # map voltage (0–15V) to angle (-120 to +120 degrees)
    angle = -120 + (voltage / 15.0) * 240
    angle_rad = radians(angle)

    # needle end
    nx = cx + int(radius * 0.8 * cos(angle_rad))
    ny = cy + int(radius * 0.8 * sin(angle_rad))

    # draw needle
    draw.line((cx, cy, nx, ny), fill="red", width=3)

    # center dot
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill="red")

    # voltage text
    draw.text((70, 180), f"{voltage:.1f}V", fill="white", font=font)


# --------------------------
# MAIN LOOP (TEST SWEEP)
# --------------------------
v = 0.0
direction = 1

while True:
    with canvas(device) as draw:
        draw_voltmeter(draw, v)

    v += direction * 0.1

    if v >= 15:
        direction = -1
    elif v <= 0:
        direction = 1

    time.sleep(0.03) 
