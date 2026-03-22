from luma.core.interface.serial import spi
from luma.lcd.device import st7789
from PIL import Image, ImageDraw
import time

# SPI setup
serial = spi(
    port=0,
    device=0,
    gpio_DC=25,
    gpio_RST=27,
    bus_speed_hz=40000000   # IMPORTANT
)

# Try different configs for GC9A01
device = st7789(
    serial,
    width=240,
    height=240,
    rotate=0,
    bgr=True,          # IMPORTANT
    h_offset=0,
    v_offset=0
)

# Create image
image = Image.new("RGB", (240, 240), "black")
draw = ImageDraw.Draw(image)

# Face
draw.ellipse((20, 20, 220, 220), fill=(255, 220, 0))

# Eyes
draw.ellipse((70, 80, 95, 105), fill="black")
draw.ellipse((145, 80, 170, 105), fill="black")

# Smile
draw.arc((60, 90, 180, 180), start=20, end=160, fill="black", width=5)

# Show
device.display(image)

while True:
    time.sleep(1)
