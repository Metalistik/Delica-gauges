import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import glob

# =================
# SETTINGS
# =================
DC = 25
RST = 27

USE_FAHRENHEIT = False
TEMP_MIN = -10
TEMP_MAX = 40

# =================
# DISPLAY INIT
# =================
GPIO.setmode(GPIO.BCM)
GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 20000000

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
    cmd(0x11)
    time.sleep(0.12)
    cmd(0x29)

def window():
    cmd(0x2A); data([0,0,0,239])
    cmd(0x2B); data([0,0,0,239])
    cmd(0x2C)

def show(img):
    window()
    GPIO.output(DC, 1)
    buf=[]
    for y in range(240):
        for x in range(240):
            r,g,b=img.getpixel((x,y))
            c=((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)
            buf += [(c>>8)&255, c&255]
    for i in range(0,len(buf),4096):
        spi.writebytes(buf[i:i+4096])

# =================
# DATA SOURCES
# =================
def location():
    try:
        j = requests.get("http://ip-api.com/json/", timeout=5).json()
        return j["lat"], j["lon"]
    except:
        return 34.68, 135.80

def weather():
    lat, lon = location()
    try:
        j = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto",
            timeout=5
        ).json()

        return (
            j["hourly"]["temperature_2m"][0],
            j["daily"]["temperature_2m_max"][0],
            j["daily"]["temperature_2m_min"][0]
        )
    except:
        return None, None, None

def sensor():
    try:
        base = glob.glob("/sys/bus/w1/devices/28-*")[0]
        with open(base+"/w1_slave") as f:
            lines = f.readlines()
        if "YES" not in lines[0]:
            return None
        return float(lines[1].split("t=")[-1])/1000
    except:
        return None

# =================
# UI HELPERS
# =================
def font(s):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    except:
        return ImageFont.load_default()

def frac(v):
    return max(0,min(1,(v-TEMP_MIN)/(TEMP_MAX-TEMP_MIN)))

def color(f):
    if f<0.5:
        return (int(255*f*2),255,80)
    return (255,int(255*(1-(f-0.5)*2)),80)

def convert(t):
    if USE_FAHRENHEIT:
        return (t*9/5)+32,"°F"
    return t,"°C"

# =================
# DRAW (FANCY AGAIN)
# =================
def draw(temp, high, low, smooth):
    img = Image.new("RGB",(240,240),(8,10,14))
    d = ImageDraw.Draw(img)

    f = frac(smooth)
    segs = 36
    lit = int(f*segs)

    for i in range(segs):
        a0 = 140 + i*(260/segs)
        a1 = a0 + (260/segs)-2

        if i<lit:
            col = color(i/segs)

            glow = Image.new("RGBA",(240,240))
            gd = ImageDraw.Draw(glow)
            gd.arc((20,20,220,220),a0,a1,fill=col+(180,),width=10)
            glow = glow.filter(ImageFilter.GaussianBlur(4))
            img.paste(glow,(0,0),glow)

        else:
            d.arc((20,20,220,220),a0,a1,fill=(40,40,45),width=8)

    d.ellipse((50,50,190,190),(12,14,20))

    t,unit = convert(temp)

    txt = f"{t:.1f}"
    f_big = font(60)
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,80),txt,font=f_big,fill=(255,255,255))

    d.text((100,140),unit,font=font(20),fill=(120,180,255))

    if high:
        ht,_=convert(high)
        lt,_=convert(low)
        d.text((75,180),f"H:{int(ht)}  L:{int(lt)}",font=font(16),fill=(180,190,210))

    return img

# =================
# MAIN LOOP
# =================
init()
smooth = 15

while True:
    s = sensor()
    w,h,l = weather()

    target = s if s is not None else w
    if target is None:
        target = smooth

    smooth += (target - smooth)*0.1

    img = draw(smooth, h, l, smooth)
    show(img)

    time.sleep(0.05)
