import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import glob

# =================
# CONFIG
# =================
DC = 25
RST = 27

TEMP_MIN = -10
TEMP_MAX = 40
USE_F = False

# =================
# DISPLAY SETUP
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
# DATA
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
            f"&current_weather=true"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto",
            timeout=5
        ).json()

        return (
            j["current_weather"]["temperature"],
            j["daily"]["temperature_2m_max"][0],
            j["daily"]["temperature_2m_min"][0],
            j["current_weather"]["weathercode"]
        )
    except:
        return None, None, None, 0

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
# HELPERS
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
    if USE_F:
        return (t*9/5)+32,"°F"
    return t,"°C"

# =================
# WEATHER ICON (ANIMATED)
# =================
def draw_icon(draw, code, frame):
    x,y = 120,55

    # simple animated cloud
    offset = int(math.sin(frame*0.2)*3)

    draw.ellipse((x-20,y-10+offset,x,y+10+offset),(200,200,200))
    draw.ellipse((x-5,y-15+offset,x+20,y+10+offset),(220,220,220))

    # rain
    if code > 50:
        for i in range(3):
            ry = y+20 + ((frame+i*3)%10)
            draw.line((x-10+i*10, ry, x-10+i*10, ry+6),(100,150,255),2)

# =================
# DRAW
# =================
def draw_ui(temp, high, low, code, smooth, frame):
    img = Image.new("RGB",(240,240),(8,10,14))
    d = ImageDraw.Draw(img)

    f = frac(smooth)
    segs = 36
    lit = int(f*segs)

    # --- RING ---
    for i in range(segs):
        a0 = 140 + i*(260/segs)
        a1 = a0 + (260/segs)-2

        if i < lit:
            col = color(i/segs)

            glow = Image.new("RGBA",(240,240))
            gd = ImageDraw.Draw(glow)
            gd.arc((20,20,220,220),a0,a1,fill=col+(200,),width=14)
            glow = glow.filter(ImageFilter.GaussianBlur(6))
            img.paste(glow,(0,0),glow)

        else:
            d.arc((20,20,220,220),a0,a1,fill=(40,40,45),width=10)

    d.ellipse((45,45,195,195),(12,14,20))

    t,unit = convert(temp)

    # BIG TEMP
    f_big = font(90)
    txt = f"{t:.1f}"
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,75),txt,font=f_big,fill=(255,255,255))

    # UNIT
    f_unit = font(32)
    d.text((105,140),unit,font=f_unit,fill=(120,180,255))

    # HIGH LOW
    if high:
        ht,_=convert(high)
        lt,_=convert(low)
        d.text((65,180),f"H:{int(ht)}  L:{int(lt)}",font=font(22),fill=(180,190,210))

    # WEATHER ICON
    draw_icon(d, code, frame)

    return img

# =================
# MAIN
# =================
init()

smooth = 15
frame = 0

while True:
    s = sensor()
    w,h,l,code = weather()

    target = s if s is not None else w
    if target is None:
        target = smooth

    smooth += (target - smooth)*0.1

    img = draw_ui(smooth, h, l, code, smooth, frame)
    show(img)

    frame += 1
    time.sleep(0.05)
