import spidev
import RPi.GPIO as GPIO
import time
import math
from PIL import Image, ImageDraw, ImageFont

DC = 25
RST = 27

TEMP_MIN = -10
TEMP_MAX = 40

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 20000000
spi.mode = 0

def command(cmd):
    GPIO.output(DC, 0)
    spi.writebytes([cmd])

def data(vals):
    GPIO.output(DC, 1)
    spi.writebytes(vals)

def reset():
    GPIO.output(RST, 1)
    time.sleep(0.05)
    GPIO.output(RST, 0)
    time.sleep(0.05)
    GPIO.output(RST, 1)
    time.sleep(0.15)

def init():
    reset()

    command(0xEF)
    command(0xEB); data([0x14])
    command(0xFE)
    command(0xEF)

    command(0xEB); data([0x14])
    command(0x84); data([0x40])
    command(0x85); data([0xFF])
    command(0x86); data([0xFF])
    command(0x87); data([0xFF])
    command(0x88); data([0x0A])
    command(0x89); data([0x21])
    command(0x8A); data([0x00])
    command(0x8B); data([0x80])
    command(0x8C); data([0x01])
    command(0x8D); data([0x01])
    command(0x8E); data([0xFF])
    command(0x8F); data([0xFF])

    command(0xB6); data([0x00, 0x20])
    command(0x36); data([0x08])
    command(0x3A); data([0x05])

    command(0x90); data([0x08, 0x08, 0x08, 0x08])
    command(0xBD); data([0x06])
    command(0xBC); data([0x00])
    command(0xFF); data([0x60, 0x01, 0x04])

    command(0xC3); data([0x13])
    command(0xC4); data([0x13])
    command(0xC9); data([0x22])

    command(0xBE); data([0x11])
    command(0xE1); data([0x10, 0x0E])

    command(0xDF); data([0x21, 0x0C, 0x02])

    command(0xF0); data([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A])
    command(0xF1); data([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F])

    command(0xF2); data([0x45, 0x09, 0x08, 0x08, 0x26, 0x2A])
    command(0xF3); data([0x43, 0x70, 0x72, 0x36, 0x37, 0x6F])

    command(0xED); data([0x1B, 0x0B])
    command(0xAE); data([0x77])
    command(0xCD); data([0x63])

    command(0x70); data([0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03])

    command(0xE8); data([0x34])
    command(0x62); data([0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70])
    command(0x63); data([0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70])
    command(0x64); data([0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07])
    command(0x66); data([0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00])
    command(0x67); data([0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98])

    command(0x74); data([0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00])

    command(0x98); data([0x3E, 0x07])

    command(0x35)
    command(0x21)
    command(0x11)
    time.sleep(0.12)
    command(0x29)
    time.sleep(0.02)

def set_window(x0, y0, x1, y1):
    command(0x2A)
    data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
    command(0x2B)
    data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
    command(0x2C)

def show_image(image):
    set_window(0, 0, 239, 239)
    GPIO.output(DC, 1)

    raw = []
    for y in range(240):
        for x in range(240):
            r, g, b = image.getpixel((x, y))
            color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw.append((color >> 8) & 0xFF)
            raw.append(color & 0xFF)

    for i in range(0, len(raw), 4096):
        spi.writebytes(raw[i:i+4096])

def get_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

def build(temp):
    img = Image.new("RGB", (240, 240), (10, 12, 18))
    d = ImageDraw.Draw(img)

    frac = max(0, min(1, (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)))
    segs = 36
    lit = int(frac * segs)

    # circular bar
    for i in range(segs):
        a0 = 140 + i * (260 / segs)
        a1 = a0 + (260 / segs) - 3

        if i < lit:
            col = (80, 200, 255) if frac < 0.5 else (255, 120, 60)
            d.arc((18, 18, 222, 222), start=a0, end=a1, fill=col, width=10)
        else:
            d.arc((18, 18, 222, 222), start=a0, end=a1, fill=(40, 40, 45), width=8)

    # center
    d.ellipse((50, 50, 190, 190), fill=(12, 14, 20))

    # BIG TEMP (this is the part that mattered)
    f_big = get_font(80)
    txt = f"{temp:.1f}"
    w, h = d.textbbox((0, 0), txt, font=f_big)[2:]
    d.text((120 - w/2, 80), txt, font=f_big, fill=(255, 255, 255))

    # unit
    f_unit = get_font(28)
    d.text((105, 140), "°C", font=f_unit, fill=(120, 180, 255))

    return img

# ===== MAIN =====
init()

temp = 10
t = 0

while True:
    t += 0.05
    temp = 10 + math.sin(t) * 10  # demo

    img = build(temp)
    show_image(img)

    time.sleep(0.05)
