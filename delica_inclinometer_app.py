#!/usr/bin/env python3
import math
import time
import pygame
from smbus2 import SMBus

# =========================
# BMI160
# =========================
ADDR = 0x69

def to_int(lo, hi):
    v = (hi << 8) | lo
    return v - 65536 if v & 0x8000 else v

bus = SMBus(1)

# BMI160 init
bus.write_byte_data(ADDR, 0x7E, 0x11)  # accel normal mode
time.sleep(0.05)
bus.write_byte_data(ADDR, 0x40, 0x28)  # accel config
bus.write_byte_data(ADDR, 0x41, 0x03)  # ±2g
time.sleep(0.03)

# =========================
# Screen / assets
# =========================
SCREEN_W = 800
SCREEN_H = 480

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Delica Inclinometer")
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("dejavusans", 32, bold=True)
font_med = pygame.font.SysFont("dejavusans", 20, bold=True)
font_small = pygame.font.SysFont("dejavusans", 16)
font_btn = pygame.font.SysFont("dejavusans", 18, bold=True)

background = pygame.image.load("background.png").convert()
background = pygame.transform.smoothscale(background, (SCREEN_W, SCREEN_H))

car_side_raw = pygame.image.load("car_side.png").convert_alpha()
car_front_raw = pygame.image.load("car_front.png").convert_alpha()

# =========================
# Layout tuning
# =========================
SIDE_BOX  = pygame.Rect(65, 85, 385, 170)
FRONT_BOX = pygame.Rect(500, 90, 190, 165)

PITCH_CENTER = (220, 400)
ROLL_CENTER  = (580, 400)
GAUGE_RADIUS = 128

ARC_START_DEG = 208.0
ARC_END_DEG   = 332.0

MAX_NEEDLE_ANGLE = 45.0
MAX_CAR_ANGLE    = 28.0

SMOOTH = 0.15

ZERO_BUTTON = pygame.Rect(680, 18, 96, 38)

# =========================
# Helpers
# =========================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def fit(img, w, h):
    iw, ih = img.get_size()
    s = min(w / iw, h / ih)
    return pygame.transform.smoothscale(img, (max(1, int(iw * s)), max(1, int(ih * s))))

class LowPass:
    def __init__(self, alpha):
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

def read_sensor():
    d = bus.read_i2c_block_data(ADDR, 0x12, 6)
    x = to_int(d[0], d[1]) / 16384.0
    y = to_int(d[2], d[3]) / 16384.0
    z = to_int(d[4], d[5]) / 16384.0

    roll = math.degrees(math.atan2(y, z))
    pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
    return roll, pitch

def gauge_theta(angle_deg):
    a = clamp(angle_deg, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)
    frac = (a + MAX_NEEDLE_ANGLE) / (2 * MAX_NEEDLE_ANGLE)
    deg = ARC_START_DEG + frac * (ARC_END_DEG - ARC_START_DEG)
    return math.radians(deg)

def pitch_color(a):
    a = abs(a)
    if a >= 30:
        return (255, 90, 70)
    if a >= 20:
        return (255, 200, 70)
    return (255, 150, 40)

def roll_color(a):
    a = abs(a)
    if a >= 30:
        return (255, 90, 70)
    if a >= 20:
        return (120, 255, 100)
    return (50, 220, 255)

def draw_glow_line(surface, color, p1, p2):
    for width, alpha in [(10, 28), (6, 60), (3, 120)]:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.line(s, (*color, alpha), p1, p2, width)
        surface.blit(s, (0, 0))
    pygame.draw.line(surface, color, p1, p2, 2)

def draw_glow_circle(surface, color, center, r):
    for rr, alpha in [(r + 7, 20), (r + 4, 50), (r + 2, 90)]:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, alpha), center, rr)
        surface.blit(s, (0, 0))
    pygame.draw.circle(surface, color, center, r)
    pygame.draw.circle(surface, (255, 255, 255), center, r, 2)

def draw_needle(surface, center, angle_deg, color):
    theta = gauge_theta(angle_deg)

    tip = (
        int(center[0] + (GAUGE_RADIUS - 8) * math.cos(theta)),
        int(center[1] + (GAUGE_RADIUS - 8) * math.sin(theta)),
    )
    tail = (
        int(center[0] - 16 * math.cos(theta)),
        int(center[1] - 16 * math.sin(theta)),
    )

    draw_glow_line(surface, color, tail, tip)
    draw_glow_circle(surface, color, tip, 5)
    draw_glow_circle(surface, (255, 255, 255), center, 3)

def draw_button(surface, rect, text, hovered=False):
    fill = (22, 28, 38) if not hovered else (34, 42, 56)
    border = (120, 180, 255) if hovered else (90, 110, 145)

    pygame.draw.rect(surface, fill, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, 2, border_radius=10)

    label = font_btn.render(text, True, (230, 240, 255))
    surface.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

# =========================
# Scale cars properly
# =========================
car_side = fit(car_side_raw, SIDE_BOX.width, SIDE_BOX.height)
car_front = fit(car_front_raw, FRONT_BOX.width, FRONT_BOX.height)

roll_lp = LowPass(SMOOTH)
pitch_lp = LowPass(SMOOTH)

roll_zero = 0.0
pitch_zero = 0.0
flash_until = 0

def zero_now():
    global roll_zero, pitch_zero, flash_until
    r, p = read_sensor()
    roll_zero = r
    pitch_zero = p
    flash_until = time.time() + 0.8

zero_now()

# =========================
# Main loop
# =========================
running = True
while running:
    mouse_pos = pygame.mouse.get_pos()
    hovered_zero = ZERO_BUTTON.collidepoint(mouse_pos)

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                running = False
            elif e.key == pygame.K_c:
                zero_now()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if ZERO_BUTTON.collidepoint(e.pos):
                zero_now()

    roll_raw, pitch_raw = read_sensor()

    roll = roll_raw - roll_zero
    pitch = pitch_raw - pitch_zero

    roll_s = roll_lp.update(roll)
    pitch_s = pitch_lp.update(pitch)

    roll_for_car = clamp(roll_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)
    pitch_for_car = clamp(pitch_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)

    roll_for_needle = clamp(roll_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)
    pitch_for_needle = clamp(pitch_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)

    screen.blit(background, (0, 0))

    # Side car = pitch only
    side_rot = pygame.transform.rotozoom(car_side, pitch_for_car, 1.0)
    side_rect = side_rot.get_rect(center=SIDE_BOX.center)
    screen.blit(side_rot, side_rect)

    # Front car = roll only
    front_rot = pygame.transform.rotozoom(car_front, -roll_for_car, 1.0)
    front_rect = front_rot.get_rect(center=FRONT_BOX.center)
    screen.blit(front_rot, front_rect)

    draw_needle(screen, PITCH_CENTER, pitch_for_needle, pitch_color(pitch_for_needle))
    draw_needle(screen, ROLL_CENTER, roll_for_needle, roll_color(roll_for_needle))

    pitch_txt = font_big.render(f"{pitch:+.1f}°", True, pitch_color(pitch_for_needle))
    roll_txt  = font_big.render(f"{roll:+.1f}°", True, roll_color(roll_for_needle))

    pitch_lbl = font_med.render("PITCH", True, pitch_color(pitch_for_needle))
    roll_lbl  = font_med.render("ROLL", True, roll_color(roll_for_needle))

    screen.blit(pitch_lbl, (PITCH_CENTER[0] - pitch_lbl.get_width() // 2, 322))
    screen.blit(roll_lbl,  (ROLL_CENTER[0]  - roll_lbl.get_width() // 2, 322))

    screen.blit(pitch_txt, (PITCH_CENTER[0] - pitch_txt.get_width() // 2, 348))
    screen.blit(roll_txt,  (ROLL_CENTER[0]  - roll_txt.get_width() // 2, 348))

    draw_button(screen, ZERO_BUTTON, "ZERO", hovered_zero)

    if time.time() < flash_until:
        msg = font_small.render("Recalibrated", True, (220, 255, 220))
        screen.blit(msg, (ZERO_BUTTON.left - msg.get_width() - 10, ZERO_BUTTON.centery - msg.get_height() // 2))

    footer = font_small.render("C = zero   ESC = quit", True, (210, 210, 210))
    screen.blit(footer, (610, 455))

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
bus.close() 
