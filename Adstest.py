#!/usr/bin/env python3

import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# Set up I2C and ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c, address=0x48)

# Use the highest gain for low voltages
ads.gain = 16

# Read channel A0
chan = AnalogIn(ads, 0)

print("Reading ADS1115 A0 (Ctrl+C to stop)\n")

while True:
    print(f"Raw: {chan.value:6d}   Voltage: {chan.voltage:.4f} V")
    time.sleep(0.5)
