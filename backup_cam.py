#!/usr/bin/env python3

import cv2
import numpy as np
import time

DEVICE = 0

cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)

if not cap.isOpened():
    print("Unable to open capture device.")
    exit(1)

window_open = False

while True:
    ret, frame = cap.read()

    signal_present = (
        ret
        and frame is not None
        and frame.size > 0
        and np.mean(frame) > 5
    )

    if signal_present:

        if not window_open:
            cv2.namedWindow("Backup Camera", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(
                "Backup Camera",
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN
            )
            window_open = True

        cv2.imshow("Backup Camera", frame)
        cv2.waitKey(1)

    else:

        if window_open:
            cv2.destroyWindow("Backup Camera")
            window_open = False

        time.sleep(0.1)

cap.release()
cv2.destroyAllWindows()
