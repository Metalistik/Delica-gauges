
import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# =========================
# SETTINGS
# =========================
DC = 25
RST = 27

# Display / UI
USE_FAHRENHEIT = False
NIGHT_MODE_AUTO = True
NIGHT_BRIGHTNESS = 0.38     # 0.0 to 1.0
DAY_BRIGHTNESS = 1.00
REFRESH_SECONDS = 0.08
WEATHER_REFRESH_SECONDS = 600   # refresh internet weather every 10 min
DISPLAY_W = 240
DISPLAY_H = 240

# Sensor / weather behavior
USE_SENSOR_IF_AVAILABLE = True
SIMULATE_IF_NO_SENSOR_AND_NO_INTERNET = True

# Your approximate location
LAT = 34.68
LON = 135.80

# Gauge range in Celsius internally
TEMP_MIN_C = -10.0
TEMP_MAX_C = 40.0

# DS18B20
# Enable 1-wire on Pi first if needed:
# sudo raspi-config -> Interface Options -> 1-Wire -> Enable
# Then reboot.
DS18B20_GLOB = "/sys/bus/w1/devices/28-*/w1_slave"

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
    # Full init sequence that works with your screen
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
    for y in range(DISPLAY_H):
        for x in range(DISPLAY_W):
            r, g, b = image.getpixel((x, y))
            color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw.append((color >> 8) & 0xFF)
            raw.append(color & 0xFF)
    return raw


def show_image(image):
    set_window(0, 0, DISPLAY_W - 1, DISPLAY_H - 1)
    GPIO.output(DC, 1)
    buf = image_to_rgb565_bytes(image)
    chunk_size = 4096
    for i in range(0, len(buf), chunk_size):
        spi.writebytes(buf[i:i + chunk_size])


# =========================
# HELPERS
# =========================
def get_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def c_to_f(c):
    return (c * 9.0 / 5.0) + 32.0


def fmt_temp(celsius):
    value = c_to_f(celsius) if USE_FAHRENHEIT else celsius
    unit = "°F" if USE_FAHRENHEIT else "°C"
    return value, unit


def temp_fraction(celsius):
    c = clamp(celsius, TEMP_MIN_C, TEMP_MAX_C)
    return (c - TEMP_MIN_C) / (TEMP_MAX_C - TEMP_MIN_C)


def temp_color(frac):
    # cold blue -> warm amber -> hot red
    if frac < 0.33:
        return (80, 145, 255)
    elif frac < 0.66:
        return (255, 185, 60)
    else:
        return (255, 90, 65)


def weather_code_to_icon(code):
    # Open-Meteo weather codes
    if code in (0, 1):
        return "sun"
    if code in (2, 3, 45, 48):
        return "cloud"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"


def is_night_time():
    hour = datetime.now().hour
    return hour >= 19 or hour < 6


def apply_brightness(img):
    if NIGHT_MODE_AUTO and is_night_time():
        return ImageEnhance.Brightness(img).enhance(NIGHT_BRIGHTNESS)
    return ImageEnhance.Brightness(img).enhance(DAY_BRIGHTNESS)


# =========================
# SENSOR
# =========================
def read_ds18b20_c():
    import glob

    matches = glob.glob(DS18B20_GLOB)
    if not matches:
        return None

    path = matches[0] + "/w1_slave"
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) < 2 or "YES" not in lines[0]:
            return None

        pos = lines[1].find("t=")
        if pos == -1:
            return None

        milli_c = int(lines[1][pos + 2:].strip())
        return milli_c / 1000.0
    except Exception:
        return None


# =========================
# INTERNET WEATHER
# =========================
def fetch_weather():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&current_weather=true"
            f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
            f"&timezone=auto"
        )
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        j = r.json()

        current_c = float(j["current_weather"]["temperature"])
        current_code = int(j["current_weather"]["weathercode"])

        high_c = float(j["daily"]["temperature_2m_max"][0])
        low_c = float(j["daily"]["temperature_2m_min"][0])

        # daily weathercode sometimes exists, but current code is OK for icon if needed
        daily_codes = j["daily"].get("weathercode", [])
        icon_code = int(daily_codes[0]) if daily_codes else current_code

        return {
            "ok": True,
            "current_c": current_c,
            "high_c": high_c,
            "low_c": low_c,
            "icon": weather_code_to_icon(icon_code if isinstance(icon_code, int) else current_code),
            "source": "NET",
        }
    except Exception:
        return {
            "ok": False,
            "current_c": None,
            "high_c": None,
            "low_c": None,
            "icon": "cloud",
            "source": "NONE",
        }


# =========================
# ICONS
# =========================
def draw_sun(draw, x=120, y=58):
    draw.ellipse((x - 17, y - 17, x + 17, y + 17), fill=(255, 205, 70))
    for i in range(8):
        a = math.radians(i * 45)
        x1 = x + math.cos(a) * 24
        y1 = y + math.sin(a) * 24
        x2 = x + math.cos(a) * 34
        y2 = y + math.sin(a) * 34
        draw.line((x1, y1, x2, y2), fill=(255, 205, 70), width=3)


def draw_cloud(draw, x=120, y=60):
    draw.ellipse((x - 30, y - 8, x - 2, y + 18), fill=(175, 180, 190))
    draw.ellipse((x - 10, y - 18, x + 18, y + 14), fill=(205, 210, 220))
    draw.ellipse((x + 5, y - 6, x + 36, y + 20), fill=(180, 185, 195))
    draw.rounded_rectangle((x - 28, y + 2, x + 30, y + 20), radius=8, fill=(185, 190, 200))


def draw_rain(draw, x=120, y=60):
    draw_cloud(draw, x, y)
    for dx in (-18, -6, 6, 18):
        draw.line((x + dx, y + 26, x + dx - 4, y + 38), fill=(80, 145, 255), width=2)


def draw_snow(draw, x=120, y=60):
    draw_cloud(draw, x, y)
    for dx in (-15, 0, 15):
        cx = x + dx
        cy = y + 32
        draw.line((cx - 4, cy, cx + 4, cy), fill=(220, 240, 255), width=2)
        draw.line((cx, cy - 4, cx, cy + 4), fill=(220, 240, 255), width=2)
        draw.line((cx - 3, cy - 3, cx + 3, cy + 3), fill=(220, 240, 255), width=1)
        draw.line((cx - 3, cy + 3, cx + 3, cy - 3), fill=(220, 240, 255), width=1)


def draw_storm(draw, x=120, y=60):
    draw_cloud(draw, x, y)
    draw.polygon([(x + 2, y + 22), (x - 8, y + 38), (x + 1, y + 38), (x - 4, y + 50), (x + 12, y + 30), (x + 3, y + 30)],
                 fill=(255, 215, 50))


def draw_icon(draw, icon):
    if icon == "sun":
        draw_sun(draw)
    elif icon == "rain":
        draw_rain(draw)
    elif icon == "snow":
        draw_snow(draw)
    elif icon == "storm":
        draw_storm(draw)
    else:
        draw_cloud(draw)


# =========================
# GLOW / UI
# =========================
def draw_glow_arc(base_img, bbox, start, end, color, width=8, blur=10):
    glow_layer = Image.new("RGBA", (DISPLAY_W, DISPLAY_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    # outer glow
    gd.arc(bbox, start=start, end=end, fill=color + (110,), width=width + 6)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=blur))
    # add core stroke
    gd = ImageDraw.Draw(glow_layer)
    gd.arc(bbox, start=start, end=end, fill=color + (255,), width=width)
    base_img.alpha_composite(glow_layer)


def status_for_temp(c):
    if c < 0:
        return "FREEZING"
    if c < 10:
        return "COLD"
    if c < 25:
        return "NORMAL"
    if c < 32:
        return "WARM"
    return "HOT"


def source_label(sensor_present, weather_ok):
    if sensor_present:
        return "PROBE + NET" if weather_ok else "PROBE ONLY"
    return "NET" if weather_ok else "SIM"


def build_frame(current_c, high_c, low_c, icon, sensor_present, weather_ok):
    img = Image.new("RGBA", (DISPLAY_W, DISPLAY_H), (10, 12, 18, 255))
    draw = ImageDraw.Draw(img)

    font_big = get_font(46)
    font_mid = get_font(18)
    font_small = get_font(12)
    font_tiny = get_font(10)

    frac = temp_fraction(current_c)
    segs = 36
    lit = int(round(frac * segs))

    # Outer frame
    draw.ellipse((8, 8, 232, 232), outline=(40, 110, 210), width=3)
    draw.ellipse((16, 16, 224, 224), outline=(28, 36, 50), width=2)

    # Segmented ring with blur glow
    start_angle = 140
    sweep = 260

    for i in range(segs):
        a0 = start_angle + i * (sweep / segs)
        a1 = a0 + (sweep / segs) - 3
        seg_frac = i / max(1, segs - 1)
        col = temp_color(seg_frac)

        if i < lit:
            draw_glow_arc(img, (18, 18, 222, 222), a0, a1, col, width=8, blur=8)
        else:
            draw.arc((18, 18, 222, 222), start=a0, end=a1, fill=(38, 40, 48), width=8)

    # Center bezel
    draw.ellipse((50, 50, 190, 190), fill=(14, 16, 23), outline=(45, 60, 90), width=2)
    draw.ellipse((58, 58, 182, 182), fill=(8, 10, 16), outline=(24, 30, 44), width=1)

    # Weather icon at top
    draw_icon(draw, icon)

    # Digital temp
    temp_value, unit = fmt_temp(current_c)
    temp_text = f"{temp_value:.1f}"
    bbox = draw.textbbox((0, 0), temp_text, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((120 - tw / 2, 95 - th / 2), temp_text, font=font_big, fill=(245, 248, 255))

    ub = draw.textbbox((0, 0), unit, font=font_mid)
    uw = ub[2] - ub[0]
    draw.text((120 - uw / 2, 132), unit, font=font_mid, fill=(120, 180, 255))

    # Status pill
    st = status_for_temp(current_c)
    st_color = temp_color(frac)
    draw.rounded_rectangle((72, 156, 168, 180), radius=10, fill=(18, 24, 35), outline=(50, 70, 110), width=1)
    sb = draw.textbbox((0, 0), st, font=font_small)
    sw = sb[2] - sb[0]
    draw.text((120 - sw / 2, 161), st, font=font_small, fill=st_color)

    # Forecast
    if high_c is not None and low_c is not None:
        hi, _ = fmt_temp(high_c)
        lo, _ = fmt_temp(low_c)
        forecast = f"H:{int(round(hi))}  L:{int(round(lo))}"
    else:
        forecast = "H:--  L:--"

    fb = draw.textbbox((0, 0), forecast, font=font_small)
    fw = fb[2] - fb[0]
    draw.text((120 - fw / 2, 190), forecast, font=font_small, fill=(180, 190, 210))

    # Bottom labels safely inside screen
    left_label = f"{int(round(c_to_f(TEMP_MIN_C) if USE_FAHRENHEIT else TEMP_MIN_C))}"
    mid_c = (TEMP_MIN_C + TEMP_MAX_C) / 2.0
    mid_label = f"{int(round(c_to_f(mid_c) if USE_FAHRENHEIT else mid_c))}"
    right_label = f"{int(round(c_to_f(TEMP_MAX_C) if USE_FAHRENHEIT else TEMP_MAX_C))}"

    draw.text((34, 212), left_label, font=font_tiny, fill=(145, 155, 175))
    mb = draw.textbbox((0, 0), mid_label, font=font_tiny)
    mw = mb[2] - mb[0]
    draw.text((120 - mw / 2, 218), mid_label, font=font_tiny, fill=(145, 155, 175))
    rb = draw.textbbox((0, 0), right_label, font=font_tiny)
    rw = rb[2] - rb[0]
    draw.text((206 - rw, 212), right_label, font=font_tiny, fill=(145, 155, 175))

    # Source label
    src = source_label(sensor_present, weather_ok)
    sb = draw.textbbox((0, 0), src, font=font_tiny)
    sw = sb[2] - sb[0]
    draw.text((120 - sw / 2, 24), src, font=font_tiny, fill=(90, 110, 145))

    out = img.convert("RGB")
    return apply_brightness(out)


# =========================
# MAIN
# =========================
def main():
    init()

    last_weather_fetch = 0
    weather = {
        "ok": False,
        "current_c": None,
        "high_c": None,
        "low_c": None,
        "icon": "cloud",
        "source": "NONE",
    }

    displayed_c = 15.0
    sim_phase = 0.0

    while True:
        now = time.time()

        # Refresh internet weather periodically
        if now - last_weather_fetch > WEATHER_REFRESH_SECONDS or not weather["ok"]:
            weather = fetch_weather()
            last_weather_fetch = now

        # Read probe if available
        sensor_c = None
        if USE_SENSOR_IF_AVAILABLE:
            sensor_c = read_ds18b20_c()

        sensor_present = sensor_c is not None
        weather_ok = weather["ok"]

        # Choose current temp source
        if sensor_present:
            target_c = sensor_c
        elif weather_ok and weather["current_c"] is not None:
            target_c = weather["current_c"]
        else:
            if SIMULATE_IF_NO_SENSOR_AND_NO_INTERNET:
                sim_phase += 0.06
                target_c = 18.0 + math.sin(sim_phase) * 8.0
            else:
                target_c = displayed_c

        # Forecast always prefers internet
        high_c = weather["high_c"] if weather_ok else None
        low_c = weather["low_c"] if weather_ok else None
        icon = weather["icon"] if weather_ok else "cloud"

        # Smooth animation
        displayed_c = (displayed_c * 0.84) + (target_c * 0.16)

        frame = build_frame(displayed_c, high_c, low_c, icon, sensor_present, weather_ok)
        show_image(frame)
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
        spi.close()
