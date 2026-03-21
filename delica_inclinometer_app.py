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
# CTRL1_XL: accel 104 Hz, ±2g
bus.write_byte_data(ADDR, 0x10, 0x40)

# CTRL3_C: BDU=1, IF_INC=1
bus.write_byte_data(ADDR, 0x12, 0x44)

time.sleep(0.1)

who = bus.read_byte_data(ADDR, 0x0F)

pygame.init()
screen = pygame.display.set_mode((800, 480))
font = pygame.font.SysFont("dejavusans", 32)
small = pygame.font.SysFont("dejavusans", 24)
clock = pygame.time.Clock()

def read_accel():
    # Read accel registers OUTX_L_XL .. OUTZ_H_XL
    d = bus.read_i2c_block_data(ADDR, 0x28, 6)

    x_raw = to_int(d[0], d[1])
    y_raw = to_int(d[2], d[3])
    z_raw = to_int(d[4], d[5])

    # ±2g => 0.061 mg/LSB
    x = x_raw * 0.000061
    y = y_raw * 0.000061
    z = z_raw * 0.000061

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y*y + z*z)))

    return x_raw, y_raw, z_raw, x, y, z, roll, pitch

while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            raise SystemExit
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            raise SystemExit

    x_raw, y_raw, z_raw, x, y, z, roll, pitch = read_accel()

    screen.fill((0, 0, 0))

    lines = [
        f"WHO_AM_I: 0x{who:02X}",
        f"X raw: {x_raw}",
        f"Y raw: {y_raw}",
        f"Z raw: {z_raw}",
        f"X g:   {x:.4f}",
        f"Y g:   {y:.4f}",
        f"Z g:   {z:.4f}",
        f"ROLL:  {roll:.2f}",
        f"PITCH: {pitch:.2f}",
        "",
        "Tilt the board now.",
        "ESC to quit.",
    ]

    y_pos = 30
    for i, line in enumerate(lines):
        surf = font.render(line, True, (255, 255, 255)) if i < 9 else small.render(line, True, (180, 180, 180))
        screen.blit(surf, (40, y_pos))
        y_pos += 38

    pygame.display.flip()
    clock.tick(20) 
