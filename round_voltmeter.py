import spidev
import RPi.GPIO as GPIO
import time

DC = 25
RST = 27

GPIO.setmode(GPIO.BCM)
GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 40000000

def command(cmd):
    GPIO.output(DC, 0)
    spi.writebytes([cmd])

def data(val):
    GPIO.output(DC, 1)
    spi.writebytes(val)

def reset():
    GPIO.output(RST, 0)
    time.sleep(0.1)
    GPIO.output(RST, 1)
    time.sleep(0.1)

def init():
    reset()
    command(0xEF)
    command(0xEB)
    data([0x14])
    command(0xFE)
    command(0xEF)
    command(0x36)
    data([0x48])
    command(0x3A)
    data([0x05])
    command(0x11)
    time.sleep(0.12)
    command(0x29)

def fill(color):
    command(0x2A)
    data([0x00,0x00,0x00,0xEF])
    command(0x2B)
    data([0x00,0x00,0x00,0xEF])
    command(0x2C)

    GPIO.output(DC, 1)
    for _ in range(240*240):
        spi.writebytes([color >> 8, color & 0xFF])

init()

# Test colors
fill(0xF800)  # red
time.sleep(2)

fill(0x07E0)  # green
time.sleep(2)

fill(0x001F)  # blue

while True:
    pass
