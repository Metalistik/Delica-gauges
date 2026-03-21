#!/usr/bin/env python3
import math, time, pygame
from smbus2 import SMBus

ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

bus = SMBus(1)

# --- INIT BMI160 ---
bus.write_byte_data(ADDR, 0x7E, 0x11)
time.sleep(0.05)
bus.write_byte_data(ADDR, 0x40, 0x28)
bus.write_byte_data(ADDR, 0x41, 0x03)

# --- PYGAME ---
pygame.init()
screen = pygame.display.set_mode((800, 480))
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("dejavusans", 36)
font_small = pygame.font.SysFont("dejavusans", 20)

# --- LOAD ASSETS ---
bg = pygame.image.load("background.png").convert()
bg = pygame.transform.scale(bg, (800, 480))

car_side = pygame.image.load("car_side.png").convert_alpha()
car_front = pygame.image.load("car_front.png").convert_alpha()

# --- POSITIONS (ADJUST ONCE IF NEEDED) ---
SIDE_POS  = (250, 200)
FRONT_POS = (550, 200)

LEFT_CENTER  = (220, 400)
RIGHT_CENTER = (580, 400)
RADIUS = 140

# --- SMOOTHING ---
roll_smooth = 0
pitch_smooth = 0
SMOOTH = 0.15

# --- SENSOR READ ---
def read():
    d = bus.read_i2c_block_data(ADDR, 0x12, 6)

    x = to_int(d[0], d[1]) * 0.000061
    y = to_int(d[2], d[3]) * 0.000061
    z = to_int(d[4], d[5]) * 0.000061

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y*y + z*z)))

    return roll, pitch

# --- CLEAN NEEDLE ---
def draw_needle(center, angle, color):
    rad = math.radians(angle)

    x = center[0] + RADIUS * math.sin(rad)
    y = center[1] - RADIUS * math.cos(rad)

    # glow
    for w in (8, 5, 3):
        pygame.draw.line(screen, (*color, 80), center, (x, y), w)

    # core line
    pygame.draw.line(screen, color, center, (x, y), 2)

    # center pivot
    pygame.draw.circle(screen, color, center, 4)

# --- MAIN LOOP ---
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            exit()

    roll, pitch = read()

    # smooth motion
    roll_smooth  += (roll  - roll_smooth)  * SMOOTH
    pitch_smooth += (pitch - pitch_smooth) * SMOOTH

    # --- DRAW BACKGROUND ---
    screen.blit(bg, (0, 0))

    # --- SIDE CAR (PITCH) ---
    side_rot = pygame.transform.rotozoom(car_side, -pitch_smooth, 1)
    side_rect = side_rot.get_rect(center=SIDE_POS)
    screen.blit(side_rot, side_rect)

    # --- FRONT CAR (ROLL) ---
    front_rot = pygame.transform.rotozoom(car_front, roll_smooth, 1)
    front_rect = front_rot.get_rect(center=FRONT_POS)
    screen.blit(front_rot, front_rect)

    # --- NEEDLES ---
    draw_needle(LEFT_CENTER, pitch_smooth, (255,120,0))
    draw_needle(RIGHT_CENTER, roll_smooth, (0,200,255))

    # --- TEXT ---
    screen.blit(font_big.render(f"{pitch_smooth:+.1f}°", True, (255,120,0)), (170, 360))
    screen.blit(font_big.render(f"{roll_smooth:+.1f}°", True, (0,200,255)), (530, 360))

    screen.blit(font_small.render("PITCH", True, (255,120,0)), (170, 330))
    screen.blit(font_small.render("ROLL", True, (0,200,255)), (530, 330))

    pygame.display.flip()
    clock.tick(30) 
