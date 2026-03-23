import spidev
import RPi.GPIO as GPIO
import time
import math
from PIL import Image, ImageDraw, ImageFont

DC = 25
RST = 27

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
    chunk_size = 4096
    for i in range(0, len(buf), chunk_size):
        spi.writebytes(buf[i:i + chunk_size])

def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    return ImageFont.load_default()

def polar(cx, cy, r, deg):
    rad = math.radians(deg)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))

def voltage_to_angle(voltage):
    # 10.0V -> 150 deg, 15.0V -> 390 deg
    v = max(10.0, min(15.0, voltage))
    return 150 + ((v - 10.0) / 5.0) * 240

def draw_delica_silhouette(draw, x, y, scale=1.0, color=(90, 150, 255)):
    pts = [
        (0, 18), (8, 10), (32, 8), (48, 7), (60, 9), (72, 15),
        (90, 15), (96, 18), (98, 24), (92, 24), (88, 20),
        (70, 20), (67, 24), (30, 24), (26, 20), (10, 20), (8, 24), (0, 24)
    ]
    scaled = [(x + px * scale, y + py * scale) for px, py in pts]
    draw.line(scaled + [scaled[0]], fill=color, width=max(1, int(2 * scale)))
    # wheels
    r = 5 * scale
    for wx in [18, 78]:
        draw.ellipse((x + (wx-r), y + (20-r), x + (wx+r), y + (20+r)), outline=color, width=max(1, int(2 * scale)))

def build_gauge_face(voltage=12.6):
    img = Image.new("RGB", (240, 240), (8, 10, 14))
    draw = ImageDraw.Draw(img)

    cx, cy = 120, 120

    # Background rings
    draw.ellipse((6, 6, 234, 234), outline=(30, 90, 180), width=4)
    draw.ellipse((14, 14, 226, 226), outline=(25, 35, 55), width=2)
    draw.ellipse((24, 24, 216, 216), fill=(12, 14, 20), outline=(45, 55, 75), width=2)

    # Accent arcs
    draw.arc((10, 10, 230, 230), start=145, end=220, fill=(220, 70, 50), width=6)
    draw.arc((10, 10, 230, 230), start=221, end=325, fill=(80, 180, 255), width=6)
    draw.arc((10, 10, 230, 230), start=326, end=395, fill=(100, 220, 120), width=6)

    # Tick marks
    for i in range(0, 51):
        value = 10.0 + i * 0.1
        ang = voltage_to_angle(value) - 90
        outer = 102
        inner = 84 if i % 5 == 0 else 90
        x1, y1 = polar(cx, cy, outer, ang)
        x2, y2 = polar(cx, cy, inner, ang)

        if value < 11.8:
            col = (220, 70, 50)
        elif value < 14.4:
            col = (100, 180, 255)
        else:
            col = (100, 220, 120)

        draw.line((x1, y1, x2, y2), fill=col, width=3 if i % 5 == 0 else 1)

    # Number labels
    font_small = get_font(14)
    font_mid = get_font(18)
    font_big = get_font(42)
    font_tiny = get_font(11)

    for val in [10, 11, 12, 13, 14, 15]:
        ang = voltage_to_angle(val) - 90
        tx, ty = polar(cx, cy, 70, ang)
        text = str(val)
        bbox = draw.textbbox((0, 0), text, font=font_small)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((tx - tw/2, ty - th/2), text, font=font_small, fill=(220, 230, 255))

    # Center bezel
    draw.ellipse((52, 52, 188, 188), fill=(18, 22, 30), outline=(50, 70, 110), width=2)
    draw.ellipse((60, 60, 180, 180), fill=(10, 12, 18), outline=(25, 35, 55), width=1)

    # Title
    title = "SPACE GEAR"
    bbox = draw.textbbox((0, 0), title, font=font_mid)
    tw = bbox[2] - bbox[0]
    draw.text((120 - tw/2, 36), title, font=font_mid, fill=(120, 180, 255))

    subtitle = "DELICA VOLTS"
    bbox = draw.textbbox((0, 0), subtitle, font=font_tiny)
    tw = bbox[2] - bbox[0]
    draw.text((120 - tw/2, 56), subtitle, font=font_tiny, fill=(150, 160, 180))

    # Delica silhouette
    draw_delica_silhouette(draw, 72, 68, scale=1.0, color=(90, 150, 255))

    # Main voltage text
    volts_text = f"{voltage:.1f}"
    bbox = draw.textbbox((0, 0), volts_text, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((120 - tw/2, 105 - th/2), volts_text, font=font_big, fill=(245, 248, 255))

    units = "V"
    bbox = draw.textbbox((0, 0), units, font=font_mid)
    uw = bbox[2] - bbox[0]
    draw.text((120 - uw/2, 136), units, font=font_mid, fill=(120, 180, 255))

    # Lower info bar
    status = "CHARGING NORMAL" if 13.2 <= voltage <= 14.7 else ("LOW BATTERY" if voltage < 12.0 else "CHECK SYSTEM")
    status_color = (100, 220, 120) if status == "CHARGING NORMAL" else ((220, 70, 50) if status == "LOW BATTERY" else (255, 190, 80))
    bbox = draw.textbbox((0, 0), status, font=font_tiny)
    sw = bbox[2] - bbox[0]
    draw.rounded_rectangle((45, 170, 195, 188), radius=8, fill=(18, 24, 35), outline=(50, 70, 110), width=1)
    draw.text((120 - sw/2, 173), status, font=font_tiny, fill=status_color)

    # Needle
    ang = voltage_to_angle(voltage) - 90
    nx, ny = polar(cx, cy, 78, ang)
    bx1, by1 = polar(cx, cy, 12, ang + 90)
    bx2, by2 = polar(cx, cy, 12, ang - 90)
    draw.polygon([(bx1, by1), (bx2, by2), (nx, ny)], fill=(255, 90, 60))
    draw.ellipse((114, 114, 126, 126), fill=(220, 230, 255), outline=(255, 90, 60), width=2)

    # Bottom tiny labels
    draw.text((35, 198), "LOW", font=font_tiny, fill=(220, 70, 50))
    draw.text((102, 198), "OK", font=font_tiny, fill=(100, 180, 255))
    draw.text((178, 198), "HIGH", font=font_tiny, fill=(100, 220, 120))

    return img

init()
img = build_gauge_face(12.6)
show_image(img)

while True:
    time.sleep(1)
