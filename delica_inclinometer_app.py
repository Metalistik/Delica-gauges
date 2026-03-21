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

# BMI160 init
bus.write_byte_data(ADDR, 0x7E, 0x11)
time.sleep(0.05)
bus.write_byte_data(ADDR, 0x40, 0x28)
bus.write_byte_data(ADDR, 0x41, 0x03)
time.sleep(0.03)

SCREEN_W = 800
SCREEN_H = 480
FPS = 30

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Delica Inclinometer")
clock = pygame.time.Clock()

font_value = pygame.font.SysFont("dejavusans", 26, bold=True)
font_label = pygame.font.SysFont("dejavusans", 17, bold=True)
font_button = pygame.font.SysFont("dejavusans", 18, bold=True)
font_small = pygame.font.SysFont("dejavusans", 14)

background = pygame.image.load("background.png").convert()
background = pygame.transform.smoothscale(background, (SCREEN_W, SCREEN_H))

car_side_raw = pygame.image.load("car_side.png").convert_alpha()
car_front_raw = pygame.image.load("car_front.png").convert_alpha()

# Layout
SIDE_BOX = pygame.Rect(78, 92, 370, 175)
FRONT_BOX = pygame.Rect(510, 95, 175, 170)

LEFT_CENTER_X = 230
RIGHT_CENTER_X = 590
CENTER_Y = 404
GAUGE_RADIUS = 88

ARC_START_DEG = 220.0
ARC_END_DEG = 320.0

MAX_NEEDLE_ANGLE = 45.0
MAX_CAR_ANGLE = 16
SMOOTH = 0.22

ZERO_BUTTON = pygame.Rect(684, 18, 96, 40)

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

def build_rotation_cache(img, min_deg, max_deg):
    cache = {}
    for deg in range(int(min_deg), int(max_deg) + 1):
        cache[deg] = pygame.transform.rotozoom(img, deg, 1.0)
    return cache

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
        return (255, 95, 70)
    if a >= 20:
        return (255, 210, 80)
    return (255, 220, 90)

def roll_color(a):
    a = abs(a)
    if a >= 30:
        return (255, 95, 70)
    if a >= 20:
        return (120, 255, 120)
    return (80, 220, 255)

def draw_button(surface, rect, text, hovered=False):
    fill = (22, 30, 42) if not hovered else (34, 44, 60)
    border = (90, 210, 255)
    pygame.draw.rect(surface, fill, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, 2, border_radius=10)
    label = font_button.render(text, True, (235, 245, 255))
    surface.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

def draw_needle(surface, center_x, center_y, angle_deg, color):
    theta = gauge_theta(angle_deg)

    tip = (
        int(center_x + GAUGE_RADIUS * math.cos(theta)),
        int(center_y + GAUGE_RADIUS * math.sin(theta)),
    )
    tail = (
        int(center_x - 6 * math.cos(theta)),
        int(center_y - 6 * math.sin(theta)),
    )

    pygame.draw.line(surface, color, tail, tip, 4)
    pygame.draw.line(surface, (255, 255, 255), tail, tip, 1)
    pygame.draw.circle(surface, color, tip, 4)
    pygame.draw.circle(surface, color, (center_x, center_y), 3)
    pygame.draw.circle(surface, (255, 255, 255), (center_x, center_y), 1)

car_side = fit(car_side_raw, SIDE_BOX.width, SIDE_BOX.height)
car_front = fit(car_front_raw, FRONT_BOX.width, FRONT_BOX.height)

SIDE_CACHE = build_rotation_cache(car_side, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)
FRONT_CACHE = build_rotation_cache(car_front, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)

roll_lp = LowPass(SMOOTH)
pitch_lp = LowPass(SMOOTH)

roll_zero = 0.0
pitch_zero = 0.0
flash_until = 0.0

def zero_now():
    global roll_zero, pitch_zero, flash_until
    r, p = read_sensor()
    roll_zero = r
    pitch_zero = p
    flash_until = time.time() + 0.8

zero_now()

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

    roll_for_car = int(round(clamp(roll_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)))
    pitch_for_car = int(round(clamp(pitch_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)))

    roll_for_needle = clamp(roll_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)
    pitch_for_needle = clamp(pitch_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)

    screen.blit(background, (0, 0))

    side_rot = SIDE_CACHE[pitch_for_car]
    side_rect = side_rot.get_rect(center=SIDE_BOX.center)
    screen.blit(side_rot, side_rect)

    front_rot = FRONT_CACHE[-roll_for_car]
    front_rect = front_rot.get_rect(center=FRONT_BOX.center)
    screen.blit(front_rot, front_rect)

    draw_needle(screen, LEFT_CENTER_X, CENTER_Y, pitch_for_needle, pitch_color(pitch_for_needle))
    draw_needle(screen, RIGHT_CENTER_X, CENTER_Y, roll_for_needle, roll_color(roll_for_needle))

    pitch_lbl = font_label.render("PITCH", True, pitch_color(pitch_for_needle))
    roll_lbl = font_label.render("ROLL", True, roll_color(roll_for_needle))

    pitch_txt = font_value.render(f"{pitch:+.1f}°", True, pitch_color(pitch_for_needle))
    roll_txt = font_value.render(f"{roll:+.1f}°", True, roll_color(roll_for_needle))

    screen.blit(pitch_lbl, (LEFT_CENTER_X - pitch_lbl.get_width() // 2, 334))
    screen.blit(roll_lbl, (RIGHT_CENTER_X - roll_lbl.get_width() // 2, 334))

    screen.blit(pitch_txt, (LEFT_CENTER_X - pitch_txt.get_width() // 2, 356))
    screen.blit(roll_txt, (RIGHT_CENTER_X - roll_txt.get_width() // 2, 356))

    draw_button(screen, ZERO_BUTTON, "ZERO", hovered_zero)

    if time.time() < flash_until:
        msg = font_small.render("Recalibrated", True, (220, 255, 220))
        screen.blit(msg, (ZERO_BUTTON.left - msg.get_width() - 8, ZERO_BUTTON.centery - msg.get_height() // 2))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
bus.close()
