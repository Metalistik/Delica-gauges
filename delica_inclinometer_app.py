#!/usr/bin/env python3
import math
import time
import pygame
from smbus2 import SMBus

# =========================
# BMI160 settings
# =========================
ADDR = 0x69

REG_CHIP_ID   = 0x00
REG_DATA_START = 0x12
REG_ACC_CONF  = 0x40
REG_ACC_RANGE = 0x41
REG_CMD       = 0x7E

CMD_ACC_NORMAL = 0x11
CMD_GYR_NORMAL = 0x15

SCREEN_W = 800
SCREEN_H = 480

# =========================
# Helpers
# =========================
def to_int16(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

class LowPass:
    def __init__(self, alpha=0.15):
        self.alpha = alpha
        self.ready = False
        self.value = 0.0

    def update(self, x):
        if not self.ready:
            self.value = x
            self.ready = True
        else:
            self.value += self.alpha * (x - self.value)
        return self.value

# =========================
# BMI160 init
# =========================
bus = SMBus(1)

chip_id = bus.read_byte_data(ADDR, REG_CHIP_ID)
if chip_id != 0xD1:
    raise RuntimeError(f"Expected BMI160 chip ID 0xD1, got 0x{chip_id:02X} at address 0x{ADDR:02X}")

# Power up accelerometer and gyro
bus.write_byte_data(ADDR, REG_CMD, CMD_ACC_NORMAL)
time.sleep(0.08)
bus.write_byte_data(ADDR, REG_CMD, CMD_GYR_NORMAL)
time.sleep(0.10)

# Accel config: 100 Hz, ±2g
bus.write_byte_data(ADDR, REG_ACC_CONF, 0x28)
time.sleep(0.02)
bus.write_byte_data(ADDR, REG_ACC_RANGE, 0x03)
time.sleep(0.02)

# =========================
# Pygame init
# =========================
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Delica Inclinometer - BMI160")
font = pygame.font.SysFont("dejavusans", 28, bold=True)
small = pygame.font.SysFont("dejavusans", 20)
clock = pygame.time.Clock()

# IMPORTANT:
# Make sure delica_overlay.png is already exactly 800x480
overlay = pygame.image.load("delica_overlay.png").convert()

# Filters
roll_filter = LowPass(0.15)
pitch_filter = LowPass(0.15)

# Zero offsets
roll_zero = 0.0
pitch_zero = 0.0

# =========================
# Sensor functions
# =========================
def read_accel():
    # BMI160 accel starts at 0x12:
    # X_L, X_H, Y_L, Y_H, Z_L, Z_H
    d = bus.read_i2c_block_data(ADDR, REG_DATA_START, 6)

    x_raw = to_int16(d[0], d[1])
    y_raw = to_int16(d[2], d[3])
    z_raw = to_int16(d[4], d[5])

    # BMI160 ±2g = 16384 LSB/g
    x = x_raw / 16384.0
    y = y_raw / 16384.0
    z = z_raw / 16384.0

    return x_raw, y_raw, z_raw, x, y, z

def compute_angles(x, y, z):
    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
    return roll, pitch

def zero_now():
    global roll_zero, pitch_zero
    _, _, _, x, y, z = read_accel()
    r, p = compute_angles(x, y, z)
    roll_zero = r
    pitch_zero = p

# =========================
# UI helpers
# =========================
def angle_color(a):
    a = abs(a)
    if a >= 30:
        return (255, 70, 70)
    if a >= 20:
        return (255, 210, 40)
    return (255, 255, 255)

def gauge_point(angle_deg, cx, cy, radius):
    """
    Tuned for your current 800x480 overlay.
    """
    angle_deg = clamp(angle_deg, -45.0, 45.0)
    frac = (angle_deg + 45.0) / 90.0
    theta = math.radians(214.0 + frac * 112.0)
    x = int(cx + radius * math.cos(theta))
    y = int(cy + radius * math.sin(theta))
    return x, y

# Zero once at startup
zero_now()

# =========================
# Main loop
# =========================
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                running = False
            elif e.key == pygame.K_c:
                zero_now()

    x_raw, y_raw, z_raw, x, y, z = read_accel()
    roll, pitch = compute_angles(x, y, z)

    roll -= roll_zero
    pitch -= pitch_zero

    roll = roll_filter.update(roll)
    pitch = pitch_filter.update(pitch)

    roll = clamp(roll, -45.0, 45.0)
    pitch = clamp(pitch, -45.0, 45.0)

    screen.blit(overlay, (0, 0))

    # Tuned to your current overlay layout
    pitch_dot = gauge_point(pitch, 235, 495, 128)
    roll_dot  = gauge_point(roll,  618, 495, 128)

    pygame.draw.circle(screen, angle_color(pitch), pitch_dot, 10)
    pygame.draw.circle(screen, (255, 255, 255), pitch_dot, 10, 2)

    pygame.draw.circle(screen, angle_color(roll), roll_dot, 10)
    pygame.draw.circle(screen, (255, 255, 255), roll_dot, 10, 2)

    # Text
    screen.blit(font.render(f"P {pitch:+.1f}", True, (255, 255, 255)), (25, 20))
    screen.blit(font.render(f"R {roll:+.1f}", True, (255, 255, 255)), (650, 20))
    screen.blit(small.render(f"CHIP 0x{chip_id:02X}", True, (220, 220, 220)), (330, 20))
    screen.blit(small.render("C = zero   ESC = quit", True, (220, 220, 220)), (560, 445))

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
bus.close()
