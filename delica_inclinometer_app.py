#!/usr/bin/env python3
import math, time, pygame
from smbus2 import SMBus

ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

bus = SMBus(1)

# Enable accelerometer
bus.write_byte_data(ADDR, 0x10, 0x60)

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

while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            exit()

    r, p = read()

    screen.blit(overlay, (0, 0))

    pygame.draw.circle(screen, (0,255,0), (220,400), 10)
    pygame.draw.circle(screen, (0,255,0), (580,400), 10)

    screen.blit(font.render(f"R {r:.1f}", True, (255,255,255)), (20,20))
    screen.blit(font.render(f"P {p:.1f}", True, (255,255,255)), (600,20))

    pygame.display.flip()
    time.sleep(0.03)
