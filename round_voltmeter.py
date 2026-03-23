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

# Set to False only if you have an ADS1115 + divider wired up
SIMULATE = True

# ADS1115 settings for real voltage reading
ADS1115_ADDR = 0x48
ADS1115_CHANNEL = 0

# Voltage divider ratio:
# Example: 100k top resistor and 20k bottom resistor
# divider_ratio = (100k + 20k) / 20k = 6.0
DIVIDER_RATIO = 6.0

# ADC reference conversion
ADS1115_LSB_4_096V = 4.096 / 32768.0

# Gauge voltage range
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


# =========================
# OPTIONAL ADS1115 SUPPORT
# =========================
try:
    import smbus2
except ImportError:
    smbus2 = None


class ADS1115Reader:
    def __init__(self, address=0x48, channel=0):
        if smbus2 is None:
            raise RuntimeError("smbus2 not installed")
        self.bus = smbus2.SMBus(1)
        self.address = address
        self.channel = channel

    def read_voltage(self):
        # MUX settings for single-ended channels
        mux_map = {
            0: 0x4000,
            1: 0x5000,
            2: 0x6000,
            3: 0x7000,
        }
        mux = mux_map.get(self.channel, 0x4000)

        # Config:
        # OS=1 start single conversion
        # MUX=selected channel
        # PGA=±4.096V
        # MODE=single-shot
        # DR=128SPS
        # COMP disabled
        config = 0x8000 | mux | 0x0200 | 0x0100 | 0x0080 | 0x0003

        config_bytes = [(config >> 8) & 0xFF, config & 0xFF]
        self.bus.write_i2c_block_data(self.address, 0x01, config_bytes)

        time.sleep(0.02)

        data = self.bus.read_i2c_block_data(self.address, 0x00, 2)
        raw = (data[0] << 8) | data[1]
        if raw > 32767:
            raw -= 65536

        adc_voltage = raw * ADS1115_LSB_4_096V
        measured_voltage = adc_voltage * DIVIDER_RATIO
        return measured_voltage


# =========================
# GAUGE DRAWING
# =========================
def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def polar(cx, cy, r, deg):
    rad = math.radians(deg)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def voltage_fraction(voltage):
    v = clamp(voltage, VOLT_MIN, VOLT_MAX)
    return (v - VOLT_MIN) / (VOLT_MAX - VOLT_MIN)


def zone_color(frac):
    # 0.0 = red, 0.5 = amber, 1.0 = green
    if frac < 0.35:
        return (235, 70, 55)
    if frac < 0.65:
        return (255, 180, 50)
    return (80, 235, 120)


def status_text(voltage):
    if voltage < 11.8:
        return "LOW"
    if voltage < 12.4:
        return "WEAK"
    if voltage <= 14.7:
        return "NORMAL"
    return "HIGH"


def draw_delica_icon(draw, x, y, scale=1.0, color=(110, 180, 255)):
    pts = [
        (0, 16), (10, 10), (28, 9), (50, 9), (62, 12), (73, 16),
        (92, 16), (98, 20), (98, 24), (89, 24), (85, 20),
        (67, 20), (63, 24), (30, 24), (26, 20), (12, 20), (9, 24), (0, 24)
    ]
    scaled = [(x + px * scale, y + py * scale) for px, py in pts]
    draw.line(scaled + [scaled[0]], fill=color, width=max(1, int(2 * scale)))
    r = 4.5 * scale
    for wx in [18, 78]:
        draw.ellipse((x + wx - r, y + 21 - r, x + wx + r, y + 21 + r), outline=color, width=max(1, int(2 * scale)))


def build_gauge_face(voltage):
    img = Image.new("RGB", (240, 240), (8, 10, 14))
    draw = ImageDraw.Draw(img)

    cx, cy = 120, 120
    frac = voltage_fraction(voltage)

    font_tiny = get_font(11)
    font_small = get_font(14)
    font_mid = get_font(18)
    font_big = get_font(44)

    # Outer frame
    draw.ellipse((4, 4, 236, 236), outline=(40, 110, 210), width=4)
    draw.ellipse((12, 12, 228, 228), outline=(30, 40, 60), width=2)
    draw.ellipse((20, 20, 220, 220), fill=(10, 12, 18), outline=(35, 45, 65), width=2)

    # Circular segmented bar graph
    start_angle = 140
    total_sweep = 260
    segments = 34
    lit_segments = int(round(frac * segments))

    for i in range(segments):
        seg_start = start_angle + (i * total_sweep / segments)
        seg_end = start_angle + ((i + 1) * total_sweep / segments) - 3

        seg_frac = i / max(1, segments - 1)
        col = zone_color(seg_frac)

        if i < lit_segments:
            width = 8
            draw.arc((18, 18, 222, 222), start=seg_start, end=seg_end, fill=col, width=width)
            draw.arc((24, 24, 216, 216), start=seg_start, end=seg_end, fill=col, width=2)
        else:
            draw.arc((18, 18, 222, 222), start=seg_start, end=seg_end, fill=(35, 38, 45), width=8)

    # Inner bezel
    draw.ellipse((48, 48, 192, 192), fill=(15, 18, 26), outline=(50, 70, 105), width=2)
    draw.ellipse((56, 56, 184, 184), fill=(8, 10, 16), outline=(24, 30, 45), width=1)

    # Top labels
    title = "DELICA SPACE GEAR"
    bbox = draw.textbbox((0, 0), title, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text((120 - tw / 2, 34), title, font=font_small, fill=(125, 190, 255))

    draw_delica_icon(draw, 70, 48, scale=1.0, color=(90, 160, 255))

    # Digital center voltage
    volts_text = f"{voltage:.2f}"
    bbox = draw.textbbox((0, 0), volts_text, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((120 - tw / 2, 104 - th / 2), volts_text, font=font_big, fill=(245, 248, 255))

    unit_text = "VOLTS"
    bbox = draw.textbbox((0, 0), unit_text, font=font_mid)
    uw = bbox[2] - bbox[0]
    draw.text((120 - uw / 2, 132), unit_text, font=font_mid, fill=(110, 180, 255))

    # Bottom status pill
    st = status_text(voltage)
    if st == "LOW":
        st_col = (235, 70, 55)
    elif st == "WEAK":
        st_col = (255, 180, 50)
    elif st == "NORMAL":
        st_col = (80, 235, 120)
    else:
        st_col = (255, 120, 60)

    draw.rounded_rectangle((62, 158, 178, 182), radius=10, fill=(18, 24, 35), outline=(50, 70, 110), width=1)
    bbox = draw.textbbox((0, 0), st, font=font_small)
    sw = bbox[2] - bbox[0]
    draw.text((120 - sw / 2, 163), st, font=font_small, fill=st_col)

    # Range labels
    draw.text((24, 192), "10V", font=font_tiny, fill=(180, 190, 210))
    draw.text((103, 202), "12.5V", font=font_tiny, fill=(180, 190, 210))
    draw.text((194, 192), "15V", font=font_tiny, fill=(180, 190, 210))

    # Tiny lower caption
    mode = "SIM MODE" if SIMULATE else "LIVE MODE"
    bbox = draw.textbbox((0, 0), mode, font=font_tiny)
    mw = bbox[2] - bbox[0]
    draw.text((120 - mw / 2, 218), mode, font=font_tiny, fill=(90, 110, 140))

    return img


# =========================
# MAIN LOOP
# =========================
def main():
    init()

    adc = None
    if not SIMULATE:
        adc = ADS1115Reader(address=ADS1115_ADDR, channel=ADS1115_CHANNEL)

    displayed_voltage = 12.60
    demo_phase = 0.0

    while True:
        try:
            if SIMULATE:
                demo_phase += 0.08
                target_voltage = 12.8 + math.sin(demo_phase) * 1.4
                target_voltage = clamp(target_voltage, VOLT_MIN, VOLT_MAX)
            else:
                target_voltage = adc.read_voltage()

            # simple smoothing
            displayed_voltage = (displayed_voltage * 0.82) + (target_voltage * 0.18)

            img = build_gauge_face(displayed_voltage)
            show_image(img)

            time.sleep(0.08)

        except KeyboardInterrupt:
            break

    GPIO.cleanup()
    spi.close()


if __name__ == "__main__":
    main() 
