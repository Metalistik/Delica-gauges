import time
import digitalio
import board
from PIL import Image
from adafruit_rgb_display import gc9a01a

print("STARTING...")

spi = board.SPI()

cs = digitalio.DigitalInOut(board.CE0)
dc = digitalio.DigitalInOut(board.D25)
rst = digitalio.DigitalInOut(board.D27)

print("INIT DISPLAY...")

disp = gc9a01a.GC9A01A(
    spi,
    cs=cs,
    dc=dc,
    rst=rst,
    width=240,
    height=240,
    baudrate=24000000
)

print("DRAWING...")

image = Image.new("RGB", (240, 240), (255, 0, 0))
disp.image(image)

print("DONE - HOLDING SCREEN")

while True:
    time.sleep(1) 
