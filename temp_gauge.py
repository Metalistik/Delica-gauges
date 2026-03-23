import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import glob

# =========================
# SETTINGS
# =========================
DC = 25
RST = 27

USE_FAHRENHEIT = False
NIGHT_MODE = True

TEMP_MIN = -10
TEMP_MAX = 40

# =========================
# DISPLAY INIT
# =========================
GPIO.setmode(GPIO.BCM)
GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 20000000

def command(cmd):
    GPIO.output(DC, 0)
    spi.writebytes([cmd])

def data(vals):
    GPIO.output(DC, 1)
    spi.writebytes(vals)

def reset():
    GPIO.output(RST, 0)
    time.sleep(0.1)
    GPIO.output(RST, 1)
    time.sleep(0.1)

def init():
    reset()
    command(0x11)
    time.sleep(0.12)
    command(0x29)

def set_window():
    command(0x2A); data([0,0,0,239])
    command(0x2B); data([0,0,0,239])
    command(0x2C)

def show(img):
    set_window()
    GPIO.output(DC, 1)
    buf = []
    for y in range(240):
        for x in range(240):
            r,g,b = img.getpixel((x,y))
            c = ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)
            buf += [(c>>8)&255, c&255]
    for i in range(0,len(buf),4096):
        spi.writebytes(buf[i:i+4096])

# =========================
# LOCATION (AUTO)
# =========================
def get_location():
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5).json()
        return r["lat"], r["lon"]
    except:
        return 34.68, 135.80  # fallback

# =========================
# WEATHER
# =========================
def weather_code_to_icon(code):
    if code < 3: return "sun"
    if code < 60: return "cloud"
    return "rain"

def fetch_weather():
    lat, lon = get_location()

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,weathercode"
            f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
            f"&timezone=auto"
        )

        j = requests.get(url, timeout=5).json()

        current = j["hourly"]["temperature_2m"][0]
        code = j["hourly"]["weathercode"][0]

        high = j["daily"]["temperature_2m_max"][0]
        low = j["daily"]["temperature_2m_min"][0]

        return current, high, low, weather_code_to_icon(code)

    except:
        return None, None, None, "cloud"

# =========================
# SENSOR
# =========================
def read_sensor():
    try:
        base = glob.glob("/sys/bus/w1/devices/28-*")[0]
        with open(base + "/w1_slave") as f:
            lines = f.readlines()

        if "YES" not in lines[0]:
            return None

        t = float(lines[1].split("t=")[-1]) / 1000.0
        return t
    except:
        return None

# =========================
# HELPERS
# =========================
def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

def frac(v):
    v = max(TEMP_MIN, min(TEMP_MAX, v))
    return (v - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)

def color(f):
    if f < 0.33: return (80,140,255)
    if f < 0.66: return (255,180,50)
    return (255,80,60)

def to_display_temp(c):
    if USE_FAHRENHEIT:
        return (c * 9/5) + 32, "°F"
    return c, "°C"

# =========================
# ICONS
# =========================
def draw_sun(d):
    d.ellipse((100,40,140,80), fill=(255,200,50))
    for i in range(8):
        a = math.radians(i*45)
        d.line((120,60,120+math.cos(a)*40,60+math.sin(a)*40), fill=(255,200,50), width=3)

def draw_cloud(d):
    d.ellipse((90,50,130,80), fill=(200,200,200))
    d.ellipse((110,40,150,80), fill=(220,220,220))

def draw_rain(d):
    draw_cloud(d)
    for i in range(4):
        d.line((100+i*15,85,95+i*15,105), fill=(80,140,255), width=2)

# =========================
# GAUGE
# =========================
def draw(temp, high, low, icon, smooth):
    img = Image.new("RGB",(240,240),(10,12,18))
    d = ImageDraw.Draw(img)

    f = frac(smooth)
    segs = 36
    lit = int(f*segs)

    for i in range(segs):
        a0 = 140 + i*(260/segs)
        a1 = a0 + (260/segs)-3

        if i < lit:
            base = color(i/segs)
            glow = tuple(min(255,int(c*1.3)) for c in base)

            layer = Image.new("RGBA",(240,240))
            ld = ImageDraw.Draw(layer)
            ld.arc((18,18,222,222),start=a0,end=a1,fill=glow+(180,),width=10)
            layer = layer.filter(ImageFilter.GaussianBlur(4))
            img.paste(layer,(0,0),layer)

        else:
            d.arc((18,18,222,222),start=a0,end=a1,fill=(40,40,45),width=8)

    d.ellipse((50,50,190,190), fill=(12,14,20))

    t, unit = to_display_temp(temp)
    txt = f"{t:.1f}"
    f_big = font(48)
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,90),txt,font=f_big,fill=(255,255,255))

    d.text((100,135),unit,font=font(18),fill=(120,180,255))

    if high:
        ht,_ = to_display_temp(high)
        lt,_ = to_display_temp(low)
        d.text((80,180),f"H:{int(ht)}  L:{int(lt)}",font=font(14),fill=(180,190,210))

    if icon == "sun": draw_sun(d)
    elif icon == "rain": draw_rain(d)
    else: draw_cloud(d)

    if NIGHT_MODE and (datetime.now().hour > 19 or datetime.now().hour < 6):
        img = ImageEnhance.Brightness(img).enhance(0.4)

    return img

# =========================
# MAIN
# =========================
init()

smooth = 15

while True:
    sensor = read_sensor()
    net_temp, high, low, icon = fetch_weather()

    if sensor is not None:
        target = sensor
    else:
        target = net_temp if net_temp else smooth

    smooth += (target - smooth) * 0.1

    img = draw(smooth, high, low, icon, smooth)
    show(img)

    time.sleep(0.05)
