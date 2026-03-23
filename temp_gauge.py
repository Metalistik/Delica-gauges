import spidev
import RPi.GPIO as GPIO
import time
import math
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
# WEATHER (fixed + stable)
# =========================
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

# =========================
# HELPERS
# =========================
def font(size):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)

def frac(v):
    return max(0,min(1,(v-TEMP_MIN)/(TEMP_MAX-TEMP_MIN)))

def color(f):
    # blue -> cyan -> yellow -> red
    if f < 0.33:
        return (80,150,255)
    elif f < 0.66:
        return (100,255,180)
    else:
        return (255,120,60)

# =========================
# SMALL CLEAN ICONS
# =========================
def draw_icon(d, code, frame):
    cx, cy = 120, 55  # keep position

    if code < 3:
        # SUN (medium size)
        d.ellipse((cx-14,cy-14,cx+14,cy+14),(255,200,0))
        for i in range(8):
            a = i*45 + frame*2
            x = cx + int(math.cos(math.radians(a))*22)
            y = cy + int(math.sin(math.radians(a))*22)
            d.line((cx,cy,x,y),(255,180,0),3)

    elif code < 50:
        # CLOUD (balanced size)
        d.ellipse((cx-22,cy-8,cx+2,cy+10),(200,200,200))
        d.ellipse((cx-6,cy-12,cx+18,cy+10),(220,220,220))

    else:
        # RAIN
        d.ellipse((cx-22,cy-8,cx+2,cy+10),(180,180,180))
        d.ellipse((cx-6,cy-12,cx+18,cy+10),(200,200,200))

        for i in range(3):
            y = cy+14 + ((frame+i*3)%10)
            d.line((cx-12+i*10,y,cx-12+i*10,y+7),(100,150,255),2)

# =========================
# MAIN DRAW (GOOD VERSION)
# =========================
def build(temp, high, low, code, smooth, frame):
    img = Image.new("RGB",(240,240),(8,10,14))
    d = ImageDraw.Draw(img)

    f = frac(smooth)
    segs = 40
    lit = int(f * segs)

    # ==== GLOW RING ====
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

    # ==== BIG TEMP ====
    f_big = font(65)
    txt = f"{temp:.1f}"
    w,h = d.textbbox((0,0),txt,font=f_big)[2:]
    d.text((120-w/2,70),txt,font=f_big,fill=(255,255,255))

    # unit
    d.text((105,135),"°C",font=font(28),fill=(120,180,255))

    # high low
    if high:
        d.text((60,180),f"H:{int(high)}  L:{int(low)}",font=font(20),fill=(180,190,210))

    # icon (FIXED SIZE + POSITION)
    draw_icon(d, code, frame)

    return img

# =========================
# MAIN LOOP
# =========================
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
