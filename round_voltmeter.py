import spidev
import RPi.GPIO as GPIO
import time
import math
from PIL import Image, ImageDraw, ImageFont

# =========================
# SETTINGS
# =========================
DC = 25
RST = 27

SIMULATE = True

VOLT_MIN = 10.0
VOLT_MAX = 15.0

# =========================
# DISPLAY DRIVER
# =========================
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
    command(0x11)
    time.sleep(0.12)
    command(0x29)


def set_window(x0, y0, x1, y1):
    command(0x2A)
    data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
    command(0x2B)
    data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
    command(0x2C)


def image_to_rgb565_bytes(image):
    image = image.convert("RGB")
    raw = []
    for y in range(240):
        for x in range(240):
            r, g, b = image.getpixel((x, y))
            color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw.append((color >> 8) & 0xFF)
            raw.append(color & 0xFF)
    return raw


def show_image(image):
    set_window(0, 0, 239, 239)
    GPIO.output(DC, 1)
    buf = image_to_rgb565_bytes(image)
    for i in range(0, len(buf), 4096):
        spi.writebytes(buf[i:i + 4096])


# =========================
# HELPERS
# =========================
def get_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def voltage_fraction(v):
    v = clamp(v, VOLT_MIN, VOLT_MAX)
    return (v - VOLT_MIN) / (VOLT_MAX - VOLT_MIN)


def zone_color(frac):
    if frac < 0.33:
        return (235, 70, 55)
    elif frac < 0.66:
        return (255, 180, 50)
    else:
        return (80, 235, 120)


# =========================
# GAUGE
# =========================
def build_gauge(voltage):
    img = Image.new("RGB", (240, 240), (10, 12, 18))
    draw = ImageDraw.Draw(img)

    cx, cy = 120, 120
    frac = voltage_fraction(voltage)

    font_big = get_font(44)
    font_mid = get_font(16)
    font_small = get_font(12)

    # outer ring
    draw.ellipse((8, 8, 232, 232), outline=(40, 110, 210), width=3)

    # segments
    start_angle = 140
    sweep = 260
    segments = 36
    lit = int(frac * segments)

    for i in range(segments):
        a0 = start_angle + i * (sweep / segments)
        a1 = a0 + (sweep / segments) - 3

        seg_frac = i / segments
        col = zone_color(seg_frac)

        if i < lit:
            draw.arc((18, 18, 222, 222), start=a0, end=a1, fill=col, width=8)
        else:
            draw.arc((18, 18, 222, 222), start=a0, end=a1, fill=(40, 40, 45), width=8)

    # center
    draw.ellipse((50, 50, 190, 190), fill=(12, 14, 20))

    # digital voltage
    txt = f"{voltage:.2f}"
    bbox = draw.textbbox((0, 0), txt, font=font_big)
    draw.text((120 - (bbox[2]-bbox[0])//2, 95), txt, font=font_big, fill=(255,255,255))

    # label
    draw.text((95, 140), "VOLTS", font=font_mid, fill=(120,180,255))

    # FIXED bottom labels (moved inward)
    draw.text((40, 195), "10V", font=font_small, fill=(180,190,210))
    draw.text((100, 205), "12.5V", font=font_small, fill=(180,190,210))
    draw.text((175, 195), "15V", font=font_small, fill=(180,190,210))

    return img


# =========================
# MAIN LOOP
# =========================
def main():
    init()

    v = 12.5
    t = 0

    while True:
        if SIMULATE:
            t += 0.08
            v = 12.8 + math.sin(t) * 1.5

        img = build_gauge(v)
        show_image(img)

        time.sleep(0.08)


if __name__ == "__main__":
    main()
