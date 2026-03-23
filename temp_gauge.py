import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from PIL import Image, ImageDraw, ImageFont

# =========================
# SETTINGS
# =========================
DC = 25
RST = 27

SIMULATE = False

LAT = 34.68
LON = 135.80

TEMP_MIN = -10
TEMP_MAX = 40

# =========================
# DISPLAY
# =========================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
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
# WEATHER
# =========================
def get_weather():
    if SIMULATE:
        t = 15 + math.sin(time.time()/8)*12
        return t, 25, 10, "sun"

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        r = requests.get(url, timeout=5).json()

        temp = r["current_weather"]["temperature"]
        high = r["daily"]["temperature_2m_max"][0]
        low = r["daily"]["temperature_2m_min"][0]

        code = r["current_weather"]["weathercode"]

        if code < 3:
            icon = "sun"
        elif code < 60:
            icon = "cloud"
        else:
            icon = "rain"

        return temp, high, low, icon
    except:
        return 20, 25, 10, "cloud"

# =========================
# DRAW HELPERS
# =========================
def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

def frac(v):
    v = max(TEMP_MIN,min(TEMP_MAX,v))
    return (v-TEMP_MIN)/(TEMP_MAX-TEMP_MIN)

def color(f):
    if f < 0.33: return (80,140,255)
    if f < 0.66: return (255,180,50)
    return (255,80,60)

# =========================
# WEATHER ICONS
# =========================
def draw_sun(draw):
    draw.ellipse((100,40,140,80), fill=(255,200,50))
    for i in range(8):
        a = math.radians(i*45)
        x1 = 120 + math.cos(a)*30
        y1 = 60 + math.sin(a)*30
        x2 = 120 + math.cos(a)*45
        y2 = 60 + math.sin(a)*45
        draw.line((x1,y1,x2,y2), fill=(255,200,50), width=3)

def draw_cloud(draw):
    draw.ellipse((90,50,130,80), fill=(180,180,180))
    draw.ellipse((110,40,150,80), fill=(200,200,200))
    draw.ellipse((120,55,170,90), fill=(170,170,170))

def draw_rain(draw):
    draw_cloud(draw)
    for i in range(4):
        draw.line((100+i*15,90,95+i*15,105), fill=(80,140,255), width=2)

# =========================
# GAUGE
# =========================
def draw_gauge(temp, high, low, icon, prev_temp):
    img = Image.new("RGB",(240,240),(10,12,18))
    d = ImageDraw.Draw(img)

    cx,cy = 120,120

    f = frac(temp)
    smooth_f = frac(prev_temp + (temp-prev_temp)*0.2)

    segs = 36
    lit = int(smooth_f * segs)

    # smooth glow ring
    for i in range(segs):
        a0 = 140 + i*(260/segs)
        a1 = a0 + (260/segs)-3

        base = color(i/segs)

        if i < lit:
            glow = tuple(min(255, int(c*1.2)) for c in base)
            d.arc((18,18,222,222),start=a0,end=a1,fill=glow,width=8)
        else:
            d.arc((18,18,222,222),start=a0,end=a1,fill=(40,40,45),width=8)

    # center
    d.ellipse((50,50,190,190), fill=(12,14,20))

    # temp text
    txt = f"{temp:.1f}"
    f_big = font(48)
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,90),txt,font=f_big,fill=(255,255,255))

    d.text((100,135),"°C",font=font(18),fill=(120,180,255))

    # forecast
    forecast = f"H:{int(high)}  L:{int(low)}"
    w,_ = d.textbbox((0,0),forecast,font=font(14))[2:]
    d.text((120-w/2,175),forecast,font=font(14),fill=(180,190,210))

    # icon
    if icon == "sun":
        draw_sun(d)
    elif icon == "cloud":
        draw_cloud(d)
    else:
        draw_rain(d)

    return img

# =========================
# MAIN LOOP
# =========================
init()

current_temp = 15

while True:
    new_temp, high, low, icon = get_weather()

    # smooth transition
    current_temp = current_temp + (new_temp - current_temp) * 0.1

    img = draw_gauge(current_temp, high, low, icon, current_temp)
    show(img)

    time.sleep(0.05)
