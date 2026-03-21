#!/usr/bin/env python3
import time
from math import sin
from PIL import Image, ImageDraw, ImageFont

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import st7789

# ----------------------------
# Display setup
# ----------------------------
serial = spi(
    port=0,
    device=0,
    gpio_DC=25,
    gpio_RST=24,
    bus_speed_hz=40000000
)

device = st7789(
    serial,
    width=240,
    height=240,
    rotate=0
)

# ----------------------------
# Fonts
# ----------------------------
try:
    big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    mid_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
except:
    big_font = ImageFont.load_default()
    mid_font = ImageFont.load_default()
    small_font = ImageFont.load_default()

# ----------------------------
# Helpers
# ----------------------------
def text_center(draw, y, text, font, fill="white"):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (240 - w) // 2
    draw.text((x, y), text, font=font, fill=fill)

def draw_ring(draw, color):
    draw.ellipse((8, 8, 232, 232), outline=color, width=4)
    draw.ellipse((20, 20, 220, 220), outline=(60, 60, 60), width=2)

def voltage_color(v):
    if v < 11.8:
        return "red"
    elif v < 12.3:
        return "yellow"
    else:
        return "cyan"

# ----------------------------
# Replace this later with real voltage reading
# ----------------------------
def get_voltage():
    # Demo value for now
    # Replace this with your actual voltage-reading code later
    t = time.time()
    return 12.6 + 0.6 * sin(t * 0.7)

# ----------------------------
# Main loop
# ----------------------------
while True:
    volts = get_voltage()
    color = voltage_color(volts)

    with canvas(device) as draw:
        # Background
        draw.ellipse((0, 0, 239, 239), fill="black")

        # Ring
        draw_ring(draw, color)

        # Label
        text_center(draw, 36, "VOLTS", mid_font, fill=(180, 180, 180))

        # Main value
        text_center(draw, 82, f"{volts:0.1f}", big_font, fill=color)

        # Unit
        text_center(draw, 156, "V", mid_font, fill=(200, 200, 200))

        # Small footer
        text_center(draw, 194, "Delica", small_font, fill=(100, 100, 100))

    time.sleep(0.05)
