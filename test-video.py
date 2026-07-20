#!/usr/bin/env python3

import subprocess
import time

SEARCH_TERMS = (
    "usb display",
    "usb ext screen",
)

def get_lsusb_output():
    try:
        result = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except Exception as error:
        print(f"Could not run lsusb: {error}")
        return ""

def dongle_connected():
    output = get_lsusb_output().lower()
    return any(term in output for term in SEARCH_TERMS)

previous_state = None

print("Watching for USB video/display dongle...")

try:
    while True:
        connected = dongle_connected()

        if connected != previous_state:
            if connected:
                print("USB capture/display dongle CONNECTED")
            else:
                print("USB capture/display dongle DISCONNECTED")

            previous_state = connected

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopped.")
