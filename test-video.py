#!/usr/bin/env python3

import glob
import os
import subprocess
import time

def list_video_devices():
    devices = sorted(glob.glob("/dev/video*"))

    results = []

    for dev in devices:
        try:
            name = subprocess.check_output(
                ["v4l2-ctl", "-D", "-d", dev],
                text=True,
                stderr=subprocess.DEVNULL
            )

            card = "Unknown"

            for line in name.splitlines():
                if line.strip().startswith("Card type"):
                    card = line.split(":", 1)[1].strip()
                    break

            results.append((dev, card))

        except Exception:
            results.append((dev, "Unknown"))

    return results


previous = None

print("Watching for USB video devices...\n")

while True:

    current = list_video_devices()

    if current != previous:

        os.system("clear")

        if not current:
            print("No video devices detected.\n")

        else:
            print("Detected video devices:\n")

            for dev, card in current:
                print(f"{dev:12}  {card}")

        previous = current

    time.sleep(1)
