#!/usr/bin/env python3
import time
from PIL import Image, ImageDraw
import spidev
import RPi.GPIO as GPIO
import gc9a01

# ----------------------------
# Pin setup
# ----------------------------
# Change these if your wiring is different
DC_PIN = 25
RST_PIN = 27
BL_PIN = 18      # backlight pin, if connected
SPI_BUS = 0
SPI_DEVICE = 0

WIDTH = 240
HEIGHT = 240

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Backlight on
    GPIO.setup(BL_PIN, GPIO.OUT)
    GPIO.output(BL_PIN, GPIO.HIGH)

    # Initialize display
    display = gc9a01.GC9A01(
        port=SPI_BUS,
        cs=SPI_DEVICE,
        dc=DC_PIN,
        rst=RST_PIN,
        width=WIDTH,
        height=HEIGHT,
        rotation=0,      # try 90, 180, or 270 if the image is rotated
        invert=False
    )

    display.init()
    display.fill(gc9a01.BLACK)

    # Create image buffer
    image = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(image)

    # Face
    draw.ellipse((20, 20, 220, 220), fill=(255, 220, 0), outline=(255, 255, 255), width=3)

    # Eyes
    draw.ellipse((70, 75, 95, 100), fill="black")
    draw.ellipse((145, 75, 170, 100), fill="black")

    # Smile
    draw.arc((65, 85, 175, 185), start=20, end=160, fill="black", width=6)

    # Push image to display
    display.display(image)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        display.fill(gc9a01.BLACK)
        GPIO.cleanup()

if __name__ == "__main__":
    main() 
