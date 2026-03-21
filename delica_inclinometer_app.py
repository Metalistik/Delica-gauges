#!/usr/bin/env python3
import math
import time
import pygame
from smbus2 import SMBus

ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

bus = SMBus(1)

# LSM6DS3 setup
bus.write_byte_data(ADDR, 0x10, 0x60)  # CTRL1_XL: accel on
bus.write_byte_data(ADDR, 0x11, 0x00)  # CTRL2_G: gyro off
bus.write_byte_data(ADDR, 0x12, 0x44)  # CTRL3_C: BDU + IF_INC

pygame.init()
screen = pygame.display.set_mode((800, 480))
font = pygame.font.SysFont("dejavusans", 30)

overlay = pygame.image.load("delica_overlay.png")
overlay = pygame.transform.scale(overlay, (800, 480))

def read():
    d = bus.read_i2c_block_data(ADDR, 0x28, 6)
    x = to_int(d[0], d[1]) * 0.000061
    y = to_int(d[2], d[3]) * 0.000061
    z = to_int(d[4], d[5]) * 0.000061

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y*y + z*z)))
    return roll, pitch

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def angle_to_arc_x(angle, cx, radius):
    angle = clamp(angle, -45, 45)
    frac = (angle + 45.0) / 90.0
    theta = math.radians(210 + frac * 120)  # left end to right end
    x = int(cx + radius * math.cos(theta))
    y = int(400 + radius * math.sin(theta))
    return x, y

while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            raise SystemExit
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            raise SystemExit

    r, p = read()

    screen.blit(overlay, (0, 0))

    # left gauge = pitch
    px, py = angle_to_arc_x(p, 220, 110)

    # right gauge = roll
    rx, ry = angle_to_arc_x(r, 580, 110)

    pygame.draw.circle(screen, (0, 255, 0), (px, py), 10)
    pygame.draw.circle(screen, (0, 255, 0), (rx, ry), 10)

    screen.blit(font.render(f"R {r:.1f}", True, (255, 255, 255)), (20, 20))
    screen.blit(font.render(f"P {p:.1f}", True, (255, 255, 255)), (680, 20))

    pygame.display.flip()
    time.sleep(0.03)
