import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ================= CONFIG =================
DC = 25
RST = 27

TEMP_MIN = -10
TEMP_MAX = 40

# ================= DISPLAY =================
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

# ================= WEATHER =================
def get_weather():
    try:
        j = requests.get(
            "https://api.open-meteo.com/v1/forecast?latitude=34.68&longitude=135.80&current_weather=true&daily=temperature_2m_max,temperature_2m_min",
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

# ================= HELPERS =================
def font(size):
    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
    )

def frac(v):
    return max(0,min(1,(v-TEMP_MIN)/(TEMP_MAX-TEMP_MIN)))

def color(f):
    if f < 0.33:
        return (80,150,255)
    elif f < 0.66:
        return (100,255,180)
    else:
        return (255,120,60)

# ================= CLEAN ICON =================
def draw_icon(d, code, frame):
    cx, cy = 120, 55

    if code < 3:
        d.ellipse((cx-12,cy-12,cx+12,cy+12),(255,200,60))
        for i in range(8):
            a = i*45 + frame*1.5
            x = cx + int(math.cos(math.radians(a))*22)
            y = cy + int(math.sin(math.radians(a))*22)
            d.line((cx,cy,x,y),(255,180,60),3)

    elif code < 50:
        d.ellipse((cx-18,cy-6,cx+2,cy+10),(200,205,210))
        d.ellipse((cx-5,cy-12,cx+18,cy+10),(220,225,230))
        d.ellipse((cx-12,cy+2,cx+12,cy+14),(190,195,200))

    else:
        d.ellipse((cx-18,cy-6,cx+2,cy+10),(180,185,190))
        d.ellipse((cx-5,cy-12,cx+18,cy+10),(200,205,210))

        for i in range(3):
            offset = (frame*2 + i*6) % 14
            x = cx - 10 + i*10
            d.line((x, cy+12+offset, x, cy+18+offset), (90,160,255), 2)

# ================= MAIN DRAW =================
def build(temp, high, low, code, smooth, frame):
    img = Image.new("RGB",(240,240),(8,10,14))
d = ImageDraw.Draw(img)

d.ellipse((8, 8, 232, 232), outline=(40, 110, 210), width=3)

# ADD THIS LINE
d.ellipse((8, 8, 232, 232), outline=(40, 110, 210), width=3)
    f = frac(smooth)
    segs = 40
    lit = int(f * segs)

    # ===== GLOW RING =====
    for i in range(segs):
        a0 = 140 + i*(260/segs)
        a1 = a0 + (260/segs)-2

        if i < lit:
            col = color(i/segs)

            glow = Image.new("RGBA",(240,240))
            gd = ImageDraw.Draw(glow)
            gd.arc((20,20,220,220),a0,a1,fill=col+(180,),width=12)
            glow = glow.filter(ImageFilter.GaussianBlur(4))

            img.paste(glow,(0,0),glow)
            d.arc((20,20,220,220),a0,a1,fill=col,width=8)

        else:
            d.arc((20,20,220,220),a0,a1,fill=(40,40,45),width=6)

    # center
    d.ellipse((45,45,195,195),(12,14,20))

    # ===== TEMP =====
    f_big = font(65)
    txt = f"{temp:.1f}"
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,75),txt,font=f_big,fill=(255,255,255))

    # unit
    d.text((105,145),"°C",font=font(28),fill=(120,180,255))

    # ===== CENTERED HIGH/LOW =====
    if high:
        text = f"H:{int(high)}  L:{int(low)}"
        f_small = font(20)
        w,h = d.textbbox((0,0),text,font=f_small)[2:]
        d.text((120 - w/2, 180), text, font=f_small, fill=(180,190,210))

    # icon
    draw_icon(d, code, frame)

    return img

# ================= MAIN =================
init()

smooth = 15
frame = 0

while True:
    temp, high, low, code = get_weather()

    if temp is None:
        temp = smooth

    smooth += (temp - smooth) * 0.12

    img = build(smooth, high, low, code, smooth, frame)
    show(img)

    frame += 1
    time.sleep(0.04)
