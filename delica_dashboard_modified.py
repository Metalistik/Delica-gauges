#!/usr/bin/env python3

import argparse
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import threading

import lgpio
import requests
import spidev
import pygame
from smbus2 import SMBus
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ============================================================
# DISPLAY / PIN CONFIGURATION
# ============================================================

WIDTH = 240
HEIGHT = 240

RST = 24
DC = 25

# Screen 1:
# Voltmeter CS -> hardware CE0

# Screen 2:
# Temperature CS -> GP26
TEMP_CS = 26

VOLT_MIN = 10.0
VOLT_MAX = 15.0

TEMP_MIN = -10.0
TEMP_MAX = 40.0

# Voltage is read from an ADS1115 when present.  If it is absent,
# the voltage gauge stays alive and shows a clean sensor-offline message.
SIMULATE_VOLTAGE = False


# ============================================================
# GPIO SETUP
# ============================================================

chip = lgpio.gpiochip_open(0)

lgpio.gpio_claim_output(chip, RST, 1)
lgpio.gpio_claim_output(chip, DC, 1)
lgpio.gpio_claim_output(chip, TEMP_CS, 1)

# Temperature screen starts deselected.
lgpio.gpio_write(chip, TEMP_CS, 1)


# ============================================================
# SPI SETUP
# ============================================================

# Screen 1 / voltmeter:
# hardware CE0
spi_volt = spidev.SpiDev()
spi_volt.open(0, 0)
spi_volt.max_speed_hz = 10_000_000
spi_volt.mode = 0

# Screen 2 / temperature:
# SPI0.1 provides SPI data/clock.
# GP26 is manually controlled as the actual screen CS.
spi_temp = spidev.SpiDev()
spi_temp.open(0, 1)
spi_temp.max_speed_hz = 10_000_000
spi_temp.mode = 0


# ============================================================
# SHARED DISPLAY LOCK
# ============================================================
#
# Both screens share:
#   DC
#   RST
#   MOSI
#   SCLK
#
# Therefore only ONE screen transaction may happen at a time.
# ============================================================

display_lock = threading.Lock()


# ============================================================
# TEMPERATURE SCREEN CHIP SELECT
# ============================================================

def temp_select():
    lgpio.gpio_write(chip, TEMP_CS, 0)


def temp_deselect():
    lgpio.gpio_write(chip, TEMP_CS, 1)


# ============================================================
# SCREEN 1 / VOLTMETER LOW-LEVEL COMMAND
# ============================================================

def volt_command(cmd, values=None):
    # Screen 2 MUST be deselected.
    temp_deselect()

    lgpio.gpio_write(chip, DC, 0)
    spi_volt.writebytes([cmd])

    if values is not None:
        lgpio.gpio_write(chip, DC, 1)
        spi_volt.writebytes(list(values))


# ============================================================
# SCREEN 2 / TEMPERATURE LOW-LEVEL COMMAND
# ============================================================

def temp_command(cmd, values=None):
    temp_select()

    lgpio.gpio_write(chip, DC, 0)
    spi_temp.writebytes([cmd])

    if values is not None:
        lgpio.gpio_write(chip, DC, 1)
        spi_temp.writebytes(list(values))

    temp_deselect()


# ============================================================
# SHARED HARDWARE RESET
# ============================================================

def reset_both_displays():
    temp_deselect()

    lgpio.gpio_write(chip, RST, 1)
    time.sleep(0.1)

    lgpio.gpio_write(chip, RST, 0)
    time.sleep(0.1)

    lgpio.gpio_write(chip, RST, 1)
    time.sleep(0.2)


# ============================================================
# GC9A01 INITIALIZATION SEQUENCE
# ============================================================

def run_init_sequence(command_function):

    command_function(0xEF)
    command_function(0xEB, [0x14])
    command_function(0xFE)
    command_function(0xEF)

    command_function(0x84, [0x40])
    command_function(0x85, [0xFF])
    command_function(0x86, [0xFF])
    command_function(0x87, [0xFF])
    command_function(0x88, [0x0A])
    command_function(0x89, [0x21])
    command_function(0x8A, [0x00])
    command_function(0x8B, [0x80])
    command_function(0x8C, [0x01])
    command_function(0x8D, [0x01])
    command_function(0x8E, [0xFF])
    command_function(0x8F, [0xFF])

    command_function(0xB6, [0x00, 0x20])

    # Keep the working display orientation.
    command_function(0x36, [0x48])

    # RGB565
    command_function(0x3A, [0x05])

    command_function(0x90, [0x08, 0x08, 0x08, 0x08])
    command_function(0xBD, [0x06])
    command_function(0xBC, [0x00])
    command_function(0xFF, [0x60, 0x01, 0x04])

    command_function(0xC3, [0x13])
    command_function(0xC4, [0x13])
    command_function(0xC9, [0x22])

    command_function(0xBE, [0x11])
    command_function(0xE1, [0x10, 0x0E])
    command_function(0xDF, [0x21, 0x0C, 0x02])

    command_function(
        0xF0,
        [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]
    )

    command_function(
        0xF1,
        [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]
    )

    command_function(
        0xF2,
        [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]
    )

    command_function(
        0xF3,
        [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]
    )

    command_function(0xED, [0x1B, 0x0B])
    command_function(0xAE, [0x77])
    command_function(0xCD, [0x63])

    command_function(
        0x70,
        [
            0x07, 0x07, 0x04,
            0x0E, 0x0F, 0x09,
            0x07, 0x08, 0x03
        ]
    )

    command_function(0xE8, [0x34])

    command_function(
        0x62,
        [
            0x18, 0x0D, 0x71, 0xED,
            0x70, 0x70, 0x18, 0x0F,
            0x71, 0xEF, 0x70, 0x70
        ]
    )

    command_function(
        0x63,
        [
            0x18, 0x11, 0x71, 0xF1,
            0x70, 0x70, 0x18, 0x13,
            0x71, 0xF3, 0x70, 0x70
        ]
    )

    command_function(
        0x64,
        [0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07]
    )

    command_function(
        0x66,
        [
            0x3C, 0x00, 0xCD, 0x67,
            0x45, 0x45, 0x10, 0x00,
            0x00, 0x00
        ]
    )

    command_function(
        0x67,
        [
            0x00, 0x3C, 0x00, 0x00,
            0x00, 0x01, 0x54, 0x10,
            0x32, 0x98
        ]
    )

    command_function(
        0x74,
        [0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00]
    )

    command_function(0x98, [0x3E, 0x07])

    command_function(0x35)
    command_function(0x21)

    command_function(0x11)
    time.sleep(0.12)

    command_function(0x29)
    time.sleep(0.05)


# ============================================================
# INITIALIZE BOTH SCREENS
# ============================================================

def init_displays():

    with display_lock:

        print("Resetting both displays...")
        reset_both_displays()

        print("Initializing voltmeter screen on CE0...")
        run_init_sequence(volt_command)

        print("Initializing temperature screen on GP26...")
        run_init_sequence(temp_command)


# ============================================================
# IMAGE CONVERSION
# ============================================================

def image_to_rgb565(image):

    output = bytearray()

    image = image.convert("RGB")

    for red, green, blue in image.getdata():

        value = (
            ((red & 0xF8) << 8)
            | ((green & 0xFC) << 3)
            | (blue >> 3)
        )

        output.append((value >> 8) & 0xFF)
        output.append(value & 0xFF)

    return output


# ============================================================
# VOLTMETER SCREEN OUTPUT
# ============================================================

def show_voltmeter(image):

    # Same software mirror correction that worked.
    image = image.transpose(
        Image.Transpose.FLIP_LEFT_RIGHT
    )

    buffer = image_to_rgb565(image)

    with display_lock:

        # Temperature screen OFF.
        temp_deselect()

        # Column window.
        volt_command(
            0x2A,
            [0x00, 0x00, 0x00, 0xEF]
        )

        # Row window.
        volt_command(
            0x2B,
            [0x00, 0x00, 0x00, 0xEF]
        )

        # Start RAM write.
        lgpio.gpio_write(chip, DC, 0)
        spi_volt.writebytes([0x2C])

        # Pixel data.
        lgpio.gpio_write(chip, DC, 1)

        for index in range(
            0,
            len(buffer),
            4096
        ):
            temp_deselect()

            spi_volt.writebytes(
                buffer[index:index + 4096]
            )


# ============================================================
# TEMPERATURE SCREEN OUTPUT
# ============================================================

def show_temperature(image):

    # Same software mirror correction.
    image = image.transpose(
        Image.Transpose.FLIP_LEFT_RIGHT
    )

    buffer = image_to_rgb565(image)

    with display_lock:

        temp_command(
            0x2A,
            [0x00, 0x00, 0x00, 0xEF]
        )

        temp_command(
            0x2B,
            [0x00, 0x00, 0x00, 0xEF]
        )

        # Select GP26 and KEEP it selected for the
        # entire framebuffer transfer.
        temp_select()

        lgpio.gpio_write(chip, DC, 0)
        spi_temp.writebytes([0x2C])

        lgpio.gpio_write(chip, DC, 1)

        for index in range(
            0,
            len(buffer),
            4096
        ):
            spi_temp.writebytes(
                buffer[index:index + 4096]
            )

        temp_deselect()


# ============================================================
# FONT
# ============================================================

def get_font(size):

    try:

        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            size
        )

    except OSError:

        return ImageFont.load_default()


# ============================================================
# VOLTMETER GAUGE
# ============================================================

def voltage_fraction(voltage):

    voltage = max(
        VOLT_MIN,
        min(VOLT_MAX, voltage)
    )

    return (
        voltage - VOLT_MIN
    ) / (
        VOLT_MAX - VOLT_MIN
    )


def voltage_zone_color(fraction):

    if fraction < 0.33:
        return (235, 70, 55)

    if fraction < 0.66:
        return (255, 180, 50)

    return (80, 235, 120)


def build_voltmeter(voltage):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (10, 12, 18)
    )

    draw = ImageDraw.Draw(image)

    fraction = voltage_fraction(voltage)

    large_font = get_font(44)
    medium_font = get_font(16)
    small_font = get_font(12)

    draw.ellipse(
        (8, 8, 232, 232),
        outline=(40, 110, 210),
        width=3
    )

    start_angle = 140
    sweep = 260
    segments = 36

    lit_segments = int(
        fraction * segments
    )

    for index in range(segments):

        angle_start = (
            start_angle
            + index
            * (sweep / segments)
        )

        angle_end = (
            angle_start
            + (sweep / segments)
            - 3
        )

        segment_color = voltage_zone_color(
            index / segments
        )

        if index < lit_segments:

            color = segment_color

        else:

            color = (40, 40, 45)

        draw.arc(
            (18, 18, 222, 222),
            start=angle_start,
            end=angle_end,
            fill=color,
            width=8
        )

    draw.ellipse(
        (50, 50, 190, 190),
        fill=(12, 14, 20)
    )

    voltage_text = f"{voltage:.2f}"

    box = draw.textbbox(
        (0, 0),
        voltage_text,
        font=large_font
    )

    text_width = box[2] - box[0]

    draw.text(
        (
            120 - text_width / 2,
            95
        ),
        voltage_text,
        font=large_font,
        fill=(255, 255, 255)
    )

    label = "VOLTS"

    box = draw.textbbox(
        (0, 0),
        label,
        font=medium_font
    )

    label_width = box[2] - box[0]

    draw.text(
        (
            120 - label_width / 2,
            140
        ),
        label,
        font=medium_font,
        fill=(120, 180, 255)
    )

    draw.text(
        (40, 195),
        "10V",
        font=small_font,
        fill=(180, 190, 210)
    )

    draw.text(
        (100, 205),
        "12.5V",
        font=small_font,
        fill=(180, 190, 210)
    )

    draw.text(
        (175, 195),
        "15V",
        font=small_font,
        fill=(180, 190, 210)
    )

    return image


# ============================================================
# WEATHER
# ============================================================

# ============================================================
# WEATHER (JMA PRIMARY, OPEN-METEO FALLBACK)
# ============================================================

DEFAULT_LATITUDE = None
DEFAULT_LONGITUDE = None
DEFAULT_TIMEZONE = "Asia/Tokyo"
DEFAULT_JMA_AREA = "290000"  # Nara Prefecture


def auto_location():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=5)
        j = r.json()
        return (
            float(j["latitude"]),
            float(j["longitude"]),
            j.get("timezone","Asia/Tokyo"),
        )
    except Exception:
        return 34.68,135.80,"Asia/Tokyo"

if DEFAULT_LATITUDE is None:
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_TIMEZONE = auto_location()


def _weather_code_from_jma(text):
    t = (text or "").lower()
    if any(k in t for k in ("rain", "shower", "雨")):
        return 61
    if any(k in t for k in ("snow", "雪")):
        return 71
    if any(k in t for k in ("cloud", "曇")):
        return 3
    if any(k in t for k in ("sun", "clear", "晴")):
        return 0
    return 2

def get_jma_forecast(area_code):
    """Return today's JMA high, low and a display weather code.

    JMA forecast JSON is authoritative for Japan.  Some area feeds omit one
    of the temperatures, so missing values are allowed and filled by the
    Open-Meteo current/fallback request below.
    """
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    response = requests.get(url, timeout=6, headers={"User-Agent": "DelicaDashboard/1.0"})
    response.raise_for_status()
    payload = response.json()
    high = low = None
    description = ""
    try:
        series = payload[0]["timeSeries"]
        weather_areas = series[0]["areas"]
        description = weather_areas[0].get("weathers", [""])[0]
        # Temperature series are normally in timeSeries[2], but area layout
        # varies. Search all series safely for temperature arrays.
        for entry in series:
            for area in entry.get("areas", []):
                temps = area.get("temps") or []
                vals = []
                for value in temps:
                    try:
                        vals.append(float(value))
                    except (TypeError, ValueError):
                        pass
                if vals:
                    low = min(vals) if low is None else min(low, min(vals))
                    high = max(vals) if high is None else max(high, max(vals))
    except (KeyError, IndexError, TypeError):
        pass
    return high, low, _weather_code_from_jma(description)

def get_open_meteo(latitude, longitude, timezone):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": timezone,
        "forecast_days": 1,
    }
    response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=6)
    response.raise_for_status()
    weather = response.json()
    current = weather.get("current", {})
    daily = weather.get("daily", {})
    return (
        current.get("temperature_2m"),
        (daily.get("temperature_2m_max") or [None])[0],
        (daily.get("temperature_2m_min") or [None])[0],
        current.get("weather_code", (daily.get("weather_code") or [0])[0]),
    )

def get_weather(latitude, longitude, timezone, jma_area):
    current = high = low = None
    code = 0
    try:
        high, low, code = get_jma_forecast(jma_area)
    except Exception as exc:
        print(f"JMA forecast unavailable: {exc}")
    try:
        om_current, om_high, om_low, om_code = get_open_meteo(latitude, longitude, timezone)
        current = om_current
        high = high if high is not None else om_high
        low = low if low is not None else om_low
        if code == 0 and om_code is not None:
            code = om_code
    except Exception as exc:
        print(f"Open-Meteo unavailable: {exc}")
    return current, high, low, code

# ============================================================
# TEMPERATURE GAUGE
# ============================================================


def temperature_fraction(value):

    return max(
        0.0,
        min(
            1.0,
            (
                value - TEMP_MIN
            ) / (
                TEMP_MAX - TEMP_MIN
            )
        )
    )


def temperature_color(value):

    if value < 0.33:
        return (80, 150, 255)

    if value < 0.66:
        return (100, 255, 180)

    return (255, 120, 60)


def draw_weather_icon(
    draw,
    code,
    frame
):

    center_x = 120
    center_y = 55

    if code < 3:

        draw.ellipse(
            (
                center_x - 12,
                center_y - 12,
                center_x + 12,
                center_y + 12
            ),
            fill=(255, 200, 60)
        )

        for index in range(8):

            angle = (
                index * 45
                + frame * 1.5
            )

            x = (
                center_x
                + int(
                    math.cos(
                        math.radians(angle)
                    ) * 22
                )
            )

            y = (
                center_y
                + int(
                    math.sin(
                        math.radians(angle)
                    ) * 22
                )
            )

            draw.line(
                (
                    center_x,
                    center_y,
                    x,
                    y
                ),
                fill=(255, 180, 60),
                width=3
            )

    elif code < 50:

        draw.ellipse(
            (
                center_x - 18,
                center_y - 6,
                center_x + 2,
                center_y + 10
            ),
            fill=(200, 205, 210)
        )

        draw.ellipse(
            (
                center_x - 5,
                center_y - 12,
                center_x + 18,
                center_y + 10
            ),
            fill=(220, 225, 230)
        )

        draw.ellipse(
            (
                center_x - 12,
                center_y + 2,
                center_x + 12,
                center_y + 14
            ),
            fill=(190, 195, 200)
        )

    else:

        draw.ellipse(
            (
                center_x - 18,
                center_y - 6,
                center_x + 2,
                center_y + 10
            ),
            fill=(180, 185, 190)
        )

        draw.ellipse(
            (
                center_x - 5,
                center_y - 12,
                center_x + 18,
                center_y + 10
            ),
            fill=(200, 205, 210)
        )

        for index in range(3):

            offset = (
                frame * 2
                + index * 6
            ) % 14

            x = (
                center_x
                - 10
                + index * 10
            )

            draw.line(
                (
                    x,
                    center_y + 12 + offset,
                    x,
                    center_y + 18 + offset
                ),
                fill=(90, 160, 255),
                width=2
            )


def build_temperature_gauge(
    temperature,
    high,
    low,
    code,
    frame
):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (8, 10, 14)
    )

    draw = ImageDraw.Draw(image)

    draw.ellipse(
        (8, 8, 232, 232),
        outline=(40, 110, 210),
        width=3
    )

    fraction = temperature_fraction(
        temperature
    )

    segments = 40

    lit_segments = int(
        fraction * segments
    )

    for index in range(segments):

        angle_start = (
            140
            + index
            * (
                260 / segments
            )
        )

        angle_end = (
            angle_start
            + (
                260 / segments
            )
            - 2
        )

        if index < lit_segments:

            segment_color = temperature_color(
                index / segments
            )

            glow = Image.new(
                "RGBA",
                (WIDTH, HEIGHT),
                (0, 0, 0, 0)
            )

            glow_draw = ImageDraw.Draw(
                glow
            )

            glow_draw.arc(
                (20, 20, 220, 220),
                angle_start,
                angle_end,
                fill=segment_color + (180,),
                width=12
            )

            glow = glow.filter(
                ImageFilter.GaussianBlur(4)
            )

            image.paste(
                glow,
                (0, 0),
                glow
            )

            draw.arc(
                (20, 20, 220, 220),
                angle_start,
                angle_end,
                fill=segment_color,
                width=8
            )

        else:

            draw.arc(
                (20, 20, 220, 220),
                angle_start,
                angle_end,
                fill=(40, 40, 45),
                width=6
            )

    draw.ellipse(
        (45, 45, 195, 195),
        fill=(12, 14, 20)
    )

    large_font = get_font(65)

    temperature_text = (
        f"{temperature:.1f}"
    )

    box = draw.textbbox(
        (0, 0),
        temperature_text,
        font=large_font
    )

    text_width = (
        box[2]
        - box[0]
    )

    draw.text(
        (
            120
            - text_width / 2,
            70
        ),
        temperature_text,
        font=large_font,
        fill=(255, 255, 255)
    )

    draw.text(
        (105, 145),
        "°C",
        font=get_font(28),
        fill=(120, 180, 255)
    )

    if (
        high is not None
        and low is not None
    ):

        high_low_text = (
            f"H:{int(high)}  "
            f"L:{int(low)}"
        )

        small_font = get_font(20)

        box = draw.textbbox(
            (0, 0),
            high_low_text,
            font=small_font
        )

        text_width = (
            box[2]
            - box[0]
        )

        draw.text(
            (
                120
                - text_width / 2,
                180
            ),
            high_low_text,
            font=small_font,
            fill=(180, 190, 210)
        )

    draw_weather_icon(
        draw,
        code,
        frame
    )

    return image


# ============================================================
# ADS1115 VOLTAGE SENSOR
# ============================================================

class ADS1115VoltageSensor:
    ADDRESS = 0x48
    REG_CONVERSION = 0x00
    REG_CONFIG = 0x01

    def __init__(self, bus_number=1, address=ADDRESS, divider_ratio=5.0, calibration=1.0):
        self.bus_number = bus_number
        self.address = address
        self.divider_ratio = divider_ratio
        self.calibration = calibration
        self.bus = None
        self.connected = False
        self.last_probe = 0.0
        self.last_error = "Not detected"

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
        self.bus = None
        self.connected = False

    def probe(self, force=False):
        now = time.monotonic()
        if not force and now - self.last_probe < 5.0:
            return self.connected
        self.last_probe = now
        self.close()
        try:
            self.bus = SMBus(self.bus_number)
            self.bus.read_i2c_block_data(self.address, self.REG_CONFIG, 2)
            self.connected = True
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)
            self.close()
        return self.connected

    def read_voltage(self):
        if not self.connected and not self.probe():
            return None
        try:
            # AIN0 vs GND, +/-4.096 V, single-shot, 128 SPS, comparator disabled.
            config = 0xC183  # +/-1.024V range
            self.bus.write_i2c_block_data(
                self.address, self.REG_CONFIG, [(config >> 8) & 0xFF, config & 0xFF]
            )
            time.sleep(0.010)
            raw_bytes = self.bus.read_i2c_block_data(self.address, self.REG_CONVERSION, 2)
            raw = (raw_bytes[0] << 8) | raw_bytes[1]
            if raw & 0x8000:
                raw -= 65536
            adc_voltage = raw * 4.096 / 32768.0
            return max(0.0, adc_voltage * self.divider_ratio * self.calibration)
        except Exception as exc:
            self.last_error = str(exc)
            self.close()
            return None


def build_voltmeter_offline():
    image = Image.new("RGB", (WIDTH, HEIGHT), (10, 12, 18))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 232, 232), outline=(75, 82, 92), width=3)
    segments = 36
    for index in range(segments):
        start = 140 + index * (260 / segments)
        draw.arc((18, 18, 222, 222), start=start, end=start + (260 / segments) - 3,
                 fill=(38, 40, 46), width=7)
    draw.ellipse((50, 50, 190, 190), fill=(12, 14, 20))
    title = "ADC"
    status = "OFFLINE"
    hint = "Connect ADS1115"
    for text, y, size, fill in (
        (title, 76, 34, (215, 220, 228)),
        (status, 116, 22, (255, 178, 72)),
        (hint, 171, 13, (165, 174, 188)),
    ):
        font = get_font(size)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((120 - (box[2] - box[0]) / 2, y), text, font=font, fill=fill)
    return image


# ============================================================
# BMI160 / INCLINOMETER
# ============================================================

BMI160_ADDR = 0x69
SCREEN_W = 800
SCREEN_H = 480
FPS = 20
SIDE_BOX = pygame.Rect(78, 92, 370, 175)
FRONT_BOX = pygame.Rect(510, 95, 175, 170)
LEFT_CENTER_X = 229
RIGHT_CENTER_X = 591
CENTER_Y = 404
MAX_NEEDLE_ANGLE = 45.0
MAX_CAR_ANGLE = 16
SMOOTH = 0.22
ZERO_BUTTON = pygame.Rect(684, 18, 96, 40)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def to_int(lo, hi):
    value = (hi << 8) | lo
    return value - 65536 if value & 0x8000 else value


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


class BMI160Sensor:
    def __init__(self, bus_number=1, address=BMI160_ADDR):
        self.bus_number = bus_number
        self.address = address
        self.bus = None
        self.connected = False
        self.last_probe = 0.0

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
        self.bus = None
        self.connected = False

    def probe(self, force=False):
        now = time.monotonic()
        if not force and now - self.last_probe < 3.0:
            return self.connected
        self.last_probe = now
        self.close()
        try:
            self.bus = SMBus(self.bus_number)
            self.bus.write_byte_data(self.address, 0x7E, 0x11)
            time.sleep(0.05)
            self.bus.write_byte_data(self.address, 0x40, 0x28)
            self.bus.write_byte_data(self.address, 0x41, 0x03)
            time.sleep(0.03)
            self.connected = True
        except Exception as exc:
            print(f"BMI160 unavailable: {exc}")
            self.close()
        return self.connected

    def read(self):
        if not self.connected and not self.probe():
            return None
        try:
            data = self.bus.read_i2c_block_data(self.address, 0x12, 6)
            x = to_int(data[0], data[1]) / 16384.0
            y = to_int(data[2], data[3]) / 16384.0
            z = to_int(data[4], data[5]) / 16384.0
            roll = math.degrees(math.atan2(y, z))
            pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
            return roll, pitch
        except Exception as exc:
            print(f"BMI160 read failed: {exc}")
            self.close()
            return None


def fit(img, width, height):
    iw, ih = img.get_size()
    scale = min(width / iw, height / ih)
    return pygame.transform.smoothscale(img, (max(1, int(iw * scale)), max(1, int(ih * scale))))


def pitch_color(angle):
    angle = abs(angle)
    if angle >= 30:
        return (255, 95, 70)
    if angle >= 20:
        return (255, 210, 80)
    return (255, 220, 90)


def roll_color(angle):
    angle = abs(angle)
    if angle >= 30:
        return (255, 95, 70)
    if angle >= 20:
        return (120, 255, 120)
    return (80, 220, 255)


def draw_button(surface, rect, text, font, hovered=False):
    fill = (22, 30, 42) if not hovered else (34, 44, 60)
    pygame.draw.rect(surface, fill, rect, border_radius=10)
    pygame.draw.rect(surface, (90, 210, 255), rect, 2, border_radius=10)
    label = font.render(text, True, (235, 245, 255))
    surface.blit(label, (rect.centerx - label.get_width() // 2,
                         rect.centery - label.get_height() // 2))


def draw_needle(surface, center_x, center_y, angle_deg, color):
    angle = clamp(angle_deg, -45.0, 45.0)
    theta = math.radians(180 + ((angle + 45.0) / 90.0) * 180)
    tip = (center_x + 118 * math.cos(theta), center_y + 78 * math.sin(theta))
    base_left = (center_x + 8 * math.cos(theta + math.pi / 2),
                 center_y + 8 * math.sin(theta + math.pi / 2))
    base_right = (center_x + 8 * math.cos(theta - math.pi / 2),
                  center_y + 8 * math.sin(theta - math.pi / 2))
    for width, alpha in ((12, 30), (8, 60)):
        glow = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.line(glow, (*color, alpha), (center_x, center_y), tip, width)
        surface.blit(glow, (0, 0))
    pygame.draw.polygon(surface, color, [base_left, base_right, tip])
    pygame.draw.line(surface, color, (center_x, center_y), tip, 3)
    pygame.draw.circle(surface, (255, 255, 255), (int(center_x), int(center_y)), 4)


def resolve_display_index(requested):
    if requested is None or str(requested).lower() == "auto":
        return 0
    try:
        return max(0, int(requested))
    except ValueError:
        pass
    try:
        output = subprocess.check_output(["xrandr", "--query"], text=True,
                                         stderr=subprocess.DEVNULL)
        names = [line.split()[0] for line in output.splitlines() if " connected" in line]
        for index, name in enumerate(names):
            if name.lower() == requested.lower():
                return index
        print(f"Display '{requested}' not found. Connected displays: {', '.join(names) or 'unknown'}")
    except Exception:
        pass
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Integrated Delica dashboard")
    parser.add_argument("--display", default="auto",
                        help="Inclinometer display: auto, display index, HDMI-1, HDMI-2, etc.")
    parser.add_argument("--fullscreen", action="store_true",
                        help="Show the inclinometer fullscreen on the selected display")
    parser.add_argument("--latitude", type=float, default=DEFAULT_LATITUDE)
    parser.add_argument("--longitude", type=float, default=DEFAULT_LONGITUDE)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--jma-area", default=DEFAULT_JMA_AREA)
    parser.add_argument("--ads-address", type=lambda x: int(x, 0), default=0x48)
    parser.add_argument("--divider-ratio", type=float, default=5.0,
                        help="Voltage-divider multiplier; 0-25V modules are normally 5.0")
    parser.add_argument("--voltage-calibration", type=float, default=1.0)
    return parser.parse_args()


def load_asset(name):
    path = Path(__file__).resolve().parent / name
    if not path.exists():
        raise FileNotFoundError(f"Required asset not found: {path}")
    return path


def cleanup_all(adc, bmi):
    adc.close()
    bmi.close()
    try:
        pygame.quit()
    except Exception:
        pass
    cleanup()


def main():
    args = parse_args()
    init_displays()

    display_index = resolve_display_index(args.display)
    pygame.init()
    flags = pygame.FULLSCREEN if args.fullscreen else 0
    try:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, display=display_index)
    except TypeError:
        # Compatibility with older pygame releases that do not accept display=.
        os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = str(display_index)
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
    pygame.display.set_caption("Delica Inclinometer")
    clock = pygame.time.Clock()

    font_value = pygame.font.SysFont("dejavusans", 26, bold=True)
    font_label = pygame.font.SysFont("dejavusans", 17, bold=True)
    font_button = pygame.font.SysFont("dejavusans", 18, bold=True)
    font_small = pygame.font.SysFont("dejavusans", 14)

    background = pygame.image.load(str(load_asset("background.png"))).convert()
    background = pygame.transform.smoothscale(background, (SCREEN_W, SCREEN_H))
    car_side = fit(pygame.image.load(str(load_asset("car_side.png"))).convert_alpha(),
                   SIDE_BOX.width, SIDE_BOX.height)
    car_front = fit(pygame.image.load(str(load_asset("car_front.png"))).convert_alpha(),
                    FRONT_BOX.width, FRONT_BOX.height)

    adc = ADS1115VoltageSensor(address=args.ads_address,
                               divider_ratio=args.divider_ratio,
                               calibration=args.voltage_calibration)
    bmi = BMI160Sensor()
    adc.probe(force=True)
    bmi.probe(force=True)

    roll_lp = LowPass(SMOOTH)
    pitch_lp = LowPass(SMOOTH)
    roll_zero = pitch_zero = 0.0
    flash_until = 0.0
    initial = bmi.read()
    if initial is not None:
        roll_zero, pitch_zero = initial

    voltage = None
    current_temperature = None
    high_temperature = None
    low_temperature = None
    weather_code = 0
    smoothed_temperature = 15.0
    last_weather_update = 0.0
    last_tft_update = 0.0
    frame = 0
    running = True

    print(f"Dashboard running. Inclinometer display index: {display_index}")
    if not adc.connected:
        print("ADS1115 not detected; voltage gauge will show ADC OFFLINE and retry automatically.")

    try:
        while running:
            now = time.monotonic()
            mouse_pos = pygame.mouse.get_pos()
            hovered_zero = ZERO_BUTTON.collidepoint(mouse_pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_c:
                        reading = bmi.read()
                        if reading is not None:
                            roll_zero, pitch_zero = reading
                            flash_until = time.time() + 0.8
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if ZERO_BUTTON.collidepoint(event.pos):
                        reading = bmi.read()
                        if reading is not None:
                            roll_zero, pitch_zero = reading
                            flash_until = time.time() + 0.8

            sensor_reading = bmi.read()
            if sensor_reading is not None:
                roll_raw, pitch_raw = sensor_reading
                roll = roll_raw - roll_zero
                pitch = pitch_raw - pitch_zero
                roll_s = roll_lp.update(roll)
                pitch_s = pitch_lp.update(pitch)
            else:
                roll = pitch = roll_s = pitch_s = 0.0

            roll_for_car = int(round(clamp(roll_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)))
            pitch_for_car = int(round(clamp(pitch_s, -MAX_CAR_ANGLE, MAX_CAR_ANGLE)))
            roll_for_needle = clamp(roll_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)
            pitch_for_needle = clamp(pitch_s, -MAX_NEEDLE_ANGLE, MAX_NEEDLE_ANGLE)

            screen.blit(background, (0, 0))
            side_rot = pygame.transform.rotate(car_side, pitch_for_car)
            screen.blit(side_rot, side_rot.get_rect(center=SIDE_BOX.center))
            front_rot = pygame.transform.rotate(car_front, -roll_for_car)
            screen.blit(front_rot, front_rot.get_rect(center=FRONT_BOX.center))
            draw_needle(screen, LEFT_CENTER_X, CENTER_Y, pitch_for_needle,
                        pitch_color(pitch_for_needle))
            draw_needle(screen, RIGHT_CENTER_X, CENTER_Y, roll_for_needle,
                        roll_color(roll_for_needle))

            pitch_lbl = font_label.render("PITCH", True, pitch_color(pitch_for_needle))
            roll_lbl = font_label.render("ROLL", True, roll_color(roll_for_needle))
            pitch_txt = font_value.render(f"{pitch:+.1f}°", True, pitch_color(pitch_for_needle))
            roll_txt = font_value.render(f"{roll:+.1f}°", True, roll_color(roll_for_needle))
            screen.blit(pitch_lbl, (LEFT_CENTER_X - pitch_lbl.get_width() // 2, 334))
            screen.blit(roll_lbl, (RIGHT_CENTER_X - roll_lbl.get_width() // 2, 334))
            screen.blit(pitch_txt, (LEFT_CENTER_X - pitch_txt.get_width() // 2, 356))
            screen.blit(roll_txt, (RIGHT_CENTER_X - roll_txt.get_width() // 2, 356))
            draw_button(screen, ZERO_BUTTON, "ZERO", font_button, hovered_zero)

            if sensor_reading is None:
                msg = font_small.render("BMI160 sensor offline", True, (255, 178, 72))
                screen.blit(msg, (20, 20))
            elif time.time() < flash_until:
                msg = font_small.render("Recalibrated", True, (220, 255, 220))
                screen.blit(msg, (ZERO_BUTTON.left - msg.get_width() - 8,
                                  ZERO_BUTTON.centery - msg.get_height() // 2))
            pygame.display.flip()

            if current_temperature is None or now - last_weather_update >= 300:
                result = get_weather(args.latitude, args.longitude, args.timezone, args.jma_area)
                if result[0] is not None:
                    current_temperature, high_temperature, low_temperature, weather_code = result
                last_weather_update = now
            if current_temperature is not None:
                smoothed_temperature += (current_temperature - smoothed_temperature) * 0.12

            if now - last_tft_update >= 0.15:
                new_voltage = adc.read_voltage()
                if not hasattr(adc,"_smooth"):
                    adc._smooth = new_voltage or 0.0
                if new_voltage is not None:
                    adc._smooth = adc._smooth*0.8 + new_voltage*0.2
                voltage = adc._smooth if new_voltage is not None else None
                volt_image = build_voltmeter(voltage) if voltage is not None else build_voltmeter_offline()
                temp_image = build_temperature_gauge(
                    smoothed_temperature, high_temperature, low_temperature, weather_code, frame
                )
                show_voltmeter(volt_image)
                show_temperature(temp_image)
                last_tft_update = now
                frame += 1

            clock.tick(FPS)
    finally:
        cleanup_all(adc, bmi)


# ============================================================
# ORIGINAL TFT CLEANUP
# ============================================================

def cleanup():
    try:
        temp_deselect()
    except Exception:
        pass
    try:
        spi_volt.close()
    except Exception:
        pass
    try:
        spi_temp.close()
    except Exception:
        pass
    try:
        lgpio.gpiochip_close(chip)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDelica dashboard stopped.")
