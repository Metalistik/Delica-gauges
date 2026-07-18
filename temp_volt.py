#!/usr/bin/env python3

import math
import time
import threading

import lgpio
import requests
import spidev
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

# Keep simulated voltage for now.
SIMULATE_VOLTAGE = True


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

def get_weather():

    try:

        response = requests.get(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=34.68"
            "&longitude=135.80"
            "&current_weather=true"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Asia%2FTokyo",
            timeout=5
        )

        response.raise_for_status()

        weather = response.json()

        return (
            weather["current_weather"]["temperature"],
            weather["daily"]["temperature_2m_max"][0],
            weather["daily"]["temperature_2m_min"][0],
            weather["current_weather"]["weathercode"]
        )

    except Exception:

        return None, None, None, 0


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
# MAIN LOOP
# ============================================================

def main():

    init_displays()

    # -------------------------
    # Voltage state
    # -------------------------

    voltage = 12.5
    voltage_timer = 0.0

    # -------------------------
    # Weather state
    # -------------------------

    smoothed_temperature = 15.0

    current_temperature = None
    high_temperature = None
    low_temperature = None
    weather_code = 0

    last_weather_update = 0.0

    frame = 0

    print("Both gauges running.")

    while True:

        loop_start = time.monotonic()

        # ====================================================
        # UPDATE VOLTAGE
        # ====================================================

        if SIMULATE_VOLTAGE:

            voltage_timer += 0.08

            voltage = (
                12.8
                + math.sin(
                    voltage_timer
                )
                * 1.5
            )

        # ====================================================
        # UPDATE WEATHER
        # ====================================================

        now = time.monotonic()

        if (
            current_temperature is None
            or now - last_weather_update >= 300
        ):

            result = get_weather()

            if result[0] is not None:

                (
                    current_temperature,
                    high_temperature,
                    low_temperature,
                    weather_code
                ) = result

            last_weather_update = now

        if current_temperature is None:

            current_temperature = (
                smoothed_temperature
            )

        smoothed_temperature += (
            current_temperature
            - smoothed_temperature
        ) * 0.12

        # ====================================================
        # BUILD BOTH IMAGES
        # ====================================================

        volt_image = build_voltmeter(
            voltage
        )

        temp_image = build_temperature_gauge(
            smoothed_temperature,
            high_temperature,
            low_temperature,
            weather_code,
            frame
        )

        # ====================================================
        # UPDATE BOTH SCREENS
        # ====================================================

        show_voltmeter(
            volt_image
        )

        show_temperature(
            temp_image
        )

        frame += 1

        # Small delay
        elapsed = (
            time.monotonic()
            - loop_start
        )

        delay = max(
            0.02,
            0.08 - elapsed
        )

        time.sleep(
            delay
        )


# ============================================================
# CLEANUP
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
        lgpio.gpiochip_close(
            chip
        )
    except Exception:
        pass


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nDual gauges stopped."
        )

    finally:

        cleanup()
