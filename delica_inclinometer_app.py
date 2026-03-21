#!/usr/bin/env python3
import math, time, pygame
from smbus2 import SMBus

ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

bus = SMBus(1)

# --- INIT BMI160 ---
bus.write_byte_data(ADDR, 0x7E, 0x11)  # accel normal mode
time.sleep(0.05)
bus.write_byte_data(ADDR, 0x40, 0x28)  # accel config
bus.write_byte_data(ADDR, 0x41, 0x03)  # ±2g

# --- PYGAME ---
pygame.init()
screen = pygame.display.set_mode((800, 480))
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("dejavusans", 36)
font_small = pygame.font.SysFont("dejavusans", 24)

overlay = pygame.image.load("delica_overlay.png")
overlay = pygame.transform.scale(overlay, (800, 480))

# --- GAUGE SETTINGS (TUNE IF NEEDED) ---
LEFT_CENTER  = (220, 400)
RIGHT_CENTER = (580, 400)
RADIUS = 140

# smoothing
roll_smooth = 0
pitch_smooth = 0
SMOOTHING = 0.15

# --- READ SENSOR ---
def read():
    d = bus.read_i2c_block_data(ADDR, 0x12, 6)

    x = to_int(d[0], d[1]) * 0.000061
    y = to_int(d[2], d[3]) * 0.000061
    z = to_int(d[4], d[5]) * 0.000061

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y*y + z*z)))

    return roll, pitch

# --- DRAW GLOW NEEDLE ---
def draw_needle(center, angle, color):
    rad = math.radians(angle)

    x = center[0] + RADIUS * math.sin(rad)
    y = center[1] - RADIUS * math.cos(rad)

    # glow layers
    for i in range(6):
        pygame.draw.line(
            screen,
            (*color, 40),
            center,
            (x, y),
            10 - i*2
        )

    # core needle
    pygame.draw.line(screen, color, center, (x, y), 3)

# --- MAIN LOOP ---
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            exit()

    roll, pitch = read()

    # smooth motion
    roll_smooth  += (roll  - roll_smooth)  * SMOOTHING
    pitch_smooth += (pitch - pitch_smooth) * SMOOTHING

    screen.fill((0, 0, 0))

    # --- CAR ANIMATION ---
    # side view = pitch
    side = pygame.transform.rotozoom(overlay, -pitch_smooth * 0.4, 1)
    rect = side.get_rect(center=(400, 240))
    screen.blit(side, rect)

    # front view = roll (subtle overlay effect)
    front = pygame.transform.rotozoom(overlay, roll_smooth * 0.2, 1)
    screen.blit(front, (0, 0), special_flags=pygame.BLEND_ADD)

    # --- NEEDLES ---
    draw_needle(LEFT_CENTER, pitch_smooth, (255, 120, 0))   # pitch
    draw_needle(RIGHT_CENTER, roll_smooth, (0, 200, 255))   # roll

    # --- TEXT ---
    screen.blit(font_big.render(f"{pitch_smooth:+.1f}°", True, (255,120,0)), (170, 360))
    screen.blit(font_big.render(f"{roll_smooth:+.1f}°", True, (0,200,255)), (530, 360))

    screen.blit(font_small.render("PITCH", True, (255,120,0)), (170, 330))
    screen.blit(font_small.render("ROLL", True, (0,200,255)), (530, 330))

    pygame.display.flip()
    clock.tick(30)
