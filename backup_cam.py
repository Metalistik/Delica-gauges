#!/usr/bin/env python3

import cv2
import numpy as np
import time

DEVICE = 0  # Change to 1 if your capture device is /dev/video1

cap = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)

if not cap.isOpened():
    print("Unable to open video capture device.")
    exit(1)

cv2.namedWindow("Backup Camera", cv2.WINDOW_NORMAL)
cv2.setWindowProperty(
    "Backup Camera",
    cv2.WND_PROP_FULLSCREEN,
    cv2.WINDOW_FULLSCREEN
)

while True:
    ret, frame = cap.read()

    if ret and frame is not None:
        # Ignore completely black frames
        if np.mean(frame) > 5:
            cv2.imshow("Backup Camera", frame)
        else:
            waiting = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                waiting,
                "Waiting for video signal...",
                (50,240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255,255,255),
                2
            )
            cv2.imshow("Backup Camera", waiting)
    else:
        waiting = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            waiting,
            "Waiting for video signal...",
            (50,240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255,255,255),
            2
        )
        cv2.imshow("Backup Camera", waiting)

    key = cv2.waitKey(30)

    if key == 27 or key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
