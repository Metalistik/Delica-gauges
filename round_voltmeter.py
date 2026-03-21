import time
import spidev
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw

DC = 25
RST = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 40000000

def cmd(c):
    GPIO.output(DC, 0)
    spi.writebytes([c])

def data(d):
    GPIO.output(DC, 1)
    spi.writebytes(d)

def reset():
    GPIO.output(RST, 0)
    time.sleep(0.1)
    GPIO.output(RST, 1)
    time.sleep(0.1)

def init():
    reset()
    cmd(0xEF)
    cmd(0xEB); data([0x14])
    cmd(0xFE)
    cmd(0xEF)
    cmd(0x36); data([0x48])
    cmd(0x3A); data([0x05])
    cmd(0x11)
    time.sleep(0.12)
    cmd(0x29)

def show(image):
    img = image.convert("RGB")
    data_bytes = list(img.tobytes())
    cmd(0x2A); data([0,0,0,239])
    cmd(0x2B); data([0,0,0,239])
    cmd(0x2C)
    data(data_bytes)

init()

while True:
    img = Image.new("RGB", (240,240), "black")
    draw = ImageDraw.Draw(img)

    # simple test
    draw.ellipse((20,20,220,220), outline="white")
    draw.text((90,110), "12.3V", fill="white")

    show(img)
    time.sleep(0.1) 
