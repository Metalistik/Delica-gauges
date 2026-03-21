#!/usr/bin/env python3
import math, time, pygame
from smbus2 import SMBus

ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

# --- SENSOR ---
bus = SMBus(1)
bus.write_byte_data(ADDR, 0x7E, 0x11)
time.sleep(0.05)
bus.write_byte_data(ADDR, 0x40, 0x28)
bus.write_byte_data(ADDR, 0x41, 0x03)

def read():
    d = bus.read_i2c_block_data(ADDR, 0x12, 6)

    x = to_int(d[0], d[1]) / 16384.0
    y = to_int(d[2], d[3]) / 16384.0
    z = to_int(d[4], d[5]) / 16384.0

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y*y + z*z)))

    return roll, pitch

# --- PYGAME ---
pygame.init()
screen = pygame.display.set_mode((800, 480))
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("dejavusans", 34, bold=True)
font_small = pygame.font.SysFont("dejavusans", 18, bold=True)

# --- LOAD FILES ---
bg = pygame.image.load("background.png").convert()
bg = pygame.transform.scale(bg, (800, 480))

car_side_raw = pygame.image.load("car_side.png").convert_alpha()
car_front_raw = pygame.image.load("car_front.png").convert_alpha()

# --- FIX SCALING (THIS WAS YOUR PROBLEM) ---
def fit(img, w, h):
    iw, ih = img.get_size()
    s = min(w/iw, h/ih)
    return pygame.transform.smoothscale(img, (int(iw*s), int(ih*s)))

car_side = fit(car_side_raw, 360, 180)
car_front = fit(car_front_raw, 180, 180)

# --- POSITIONS ---
SIDE_POS = (250, 200)
FRONT_POS = (560, 200)

PITCH_CENTER = (220, 400)
ROLL_CENTER  = (580, 400)
RADIUS = 130

# --- SMOOTH ---
roll_s = 0
pitch_s = 0
SMOOTH = 0.15

# --- NEEDLE ---
def needle(center, angle, color):
    r = math.radians(angle)
    x = center[0] + RADIUS * math.sin(r)
    y = center[1] - RADIUS * math.cos(r)

    # glow
    for w in (8,5,3):
        s = pygame.Surface((800,480), pygame.SRCALPHA)
        pygame.draw.line(s, (*color, 80), center, (x,y), w)
        screen.blit(s,(0,0))

    pygame.draw.line(screen, color, center, (x,y), 2)
    pygame.draw.circle(screen, color, center, 4)

# --- LOOP ---
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            exit()

    roll, pitch = read()

    roll_s  += (roll  - roll_s)  * SMOOTH
    pitch_s += (pitch - pitch_s) * SMOOTH

    # --- DRAW ORDER (CRITICAL FIX) ---
    screen.blit(bg, (0,0))   # background FIRST

    # --- CARS ---
    side = pygame.transform.rotozoom(car_side, -pitch_s, 1)
    screen.blit(side, side.get_rect(center=SIDE_POS))

    front = pygame.transform.rotozoom(car_front, roll_s, 1)
    screen.blit(front, front.get_rect(center=FRONT_POS))

    # --- NEEDLES ---
    needle(PITCH_CENTER, pitch_s, (255,140,0))
    needle(ROLL_CENTER,  roll_s,  (0,200,255))

    # --- TEXT ---
    screen.blit(font_big.render(f"{pitch_s:+.1f}°", True, (255,140,0)), (160,350))
    screen.blit(font_big.render(f"{roll_s:+.1f}°",  True, (0,200,255)), (520,350))

    screen.blit(font_small.render("PITCH", True, (255,140,0)), (160,320))
    screen.blit(font_small.render("ROLL",  True, (0,200,255)), (520,320))

    pygame.display.flip()
    clock.tick(30) 
