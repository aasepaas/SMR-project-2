import cv2
import numpy as np
from pylibdmtx.pylibdmtx import decode
from PIL import Image
import sys
import threading
import time

# Global variables for threading
decode_result = None
decode_lock = threading.Lock()
last_decode_time = 0


def decode_thread(frame):
    global decode_result
    try:
        results = decode(frame)
        with decode_lock:
            decode_result = results
    except Exception as e:
        print("Decode error:", e)
        with decode_lock:
            decode_result = None


def data_matrix_demo(cap):
    global last_decode_time

    window_name = "datamatrix scanner"
    frame_number = 0
    need_to_save = False
    last_code = None

    while True:
        e1 = cv2.getTickCount()

        ret, frame = cap.read()
        if not ret:
            break

        imr = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_CUBIC)
        imdecode = imr.copy()

        # Get center coordinates
        height, width = imr.shape[:2]
        center_x = width // 2
        center_y = height // 2

        # ROI size (smaller)
        roi_width = 80
        roi_height = 40

        try:
            # ROI area in center
            x1 = center_x - roi_width // 2
            x2 = center_x + roi_width // 2
            y1 = center_y - roi_height // 2
            y2 = center_y + roi_height // 2

            roi = imr[y1:y2, x1:x2]
            means = cv2.mean(roi)
            mean_value = int(means[0])

            # Drawing for visualization
            cv2.rectangle(imr, (x1, y1), (x2, y2), (255, 255, 255), 1)
            cv2.line(imr, (center_x, y1 - 10), (center_x, y2 + 10), (0, 0, 255), 1)
            cv2.line(imr, (x1 - 10, center_y), (x2 + 10, center_y), (0, 0, 255), 1)
            cv2.putText(imr, str(mean_value), (center_x - 30, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 0, 0), 1)

            # Condition for triggering decode - start decode in separate thread
            if 100 < mean_value < 190:
                # Start decode every 0.3 seconds to avoid too many threads
                if time.time() - last_decode_time > 0.3:
                    threading.Thread(target=decode_thread, args=(imdecode.copy(),), daemon=True).start()
                    last_decode_time = time.time()

            # Check if we have decode results
            with decode_lock:
                if decode_result:
                    results = decode_result
                    if results:
                        result = results[0]
                        last_code = result.data.decode("utf-8")
                        points = result.rect

                        # draw rectangle
                        x, y, w, h = points
                        cv2.rectangle(imr, (x, y), (x + w, y + h), (0, 255, 0), 2)

                        # print code on screen
                        cv2.putText(imr, last_code, (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)

        except Exception as e:
            print("Processing error:", e)

        # FPS Counter
        e2 = cv2.getTickCount()
        t = (e2 - e1) / cv2.getTickFrequency()
        fps = int(1 / t) if t > 0 else 0
        cv2.rectangle(imr, (0, 0), (110, 14), (0, 0, 0), -1)
        cv2.putText(imr, f"{t:.3f}s {fps}fps", (1, 10),
                    cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 250, 0), 1)

        cv2.imshow(window_name, imr)
        key = cv2.waitKey(1)

        if key in [ord('q'), ord('Q'), 27]:
            break

        if key == 32:
            need_to_save = True

        if need_to_save and last_code:
            filename = f"datamatrix{frame_number:03d}.jpg"
            cv2.imwrite(filename, frame)
            print("Saved frame to", filename)
            need_to_save = False

        frame_number += 1


if __name__ == '__main__':
    print(__doc__)

    if len(sys.argv) == 1:
        cap = cv2.VideoCapture(1)
    else:
        cap = cv2.VideoCapture(sys.argv[1])
        if not cap.isOpened():
            cap = cv2.VideoCapture(int(sys.argv[1]))

    if not cap.isOpened():
        print('Cannot initialize video capture')
        sys.exit(-1)

    # Set resolution to 1080p
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

    data_matrix_demo(cap)
