import cv2
import numpy as np
from pylibdmtx.pylibdmtx import decode
from multiprocessing import Process, Queue
import sys
import time

# Decode function for multiprocessing
def decode_process(frame, result_queue):
    try:
        results = decode(frame)
        if results:
            result_queue.put(results[0])
        else:
            result_queue.put(None)
    except Exception as e:
        print("Decode error:", e)
        result_queue.put(None)

def data_matrix_demo(cap):
    frame_number = 0
    last_code = None
    last_decode_time = 0
    result_queue = Queue()
    decode_proc = None

    window_name = "Datamatrix scanner"

    while True:
        e1 = cv2.getTickCount()

        ret, frame = cap.read()
        if not ret:
            break

        # Resize for faster processing
        RESIZE = 1
        imr = cv2.resize(frame, None, fx=RESIZE, fy=RESIZE, interpolation=cv2.INTER_CUBIC)
        imdecode = imr.copy()
        # ROI calculation
        height, width = imr.shape[:2]
        center_x, center_y = width // 2, height // 2
        roi_width, roi_height = 80, 80
        x1, x2 = center_x - roi_width // 2, center_x + roi_width // 2
        y1, y2 = center_y - roi_height // 2, center_y + roi_height // 2

        roi = imr[y1:y2, x1:x2]
        mean_value = int(cv2.mean(roi)[0])

        # Visualization
        # print(height, width)
        top = 550
        bottom = 650
        left = 800
        right = 900
        frame = cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2, 1)
        imr = imr[top:bottom, left:right]
        # imr = cv2.resize(imr, ((bottom-top)*4, (right-left)*4))
        
        # cv2.rectangle(imr, (x1, y1), (x2, y2), (255, 255, 255), 1)
        # cv2.line(imr, (center_x, y1 - 10), (center_x, y2 + 10), (0, 0, 255), 1)
        # cv2.line(imr, (x1 - 10, center_y), (x2 + 10, center_y), (0, 0, 255), 1)
        # center_x = (right-left)//2
        cv2.putText(imr, str(mean_value), (center_x - 30, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 0, 0), 1)
        # print(f"Mean Value: {mean_value}")
        # Start decode process every 0.3s
        # if 40 < mean_value < 80 and (time.time() - last_decode_time > 0.3):
        if time.time() - last_decode_time > 0.1:
            if decode_proc is None or not decode_proc.is_alive():
                decode_proc = Process(target=decode_process, args=(imdecode.copy(), result_queue))
                decode_proc.start()
                last_decode_time = time.time()

        # Check for decode results
        if not result_queue.empty():
            result = result_queue.get()
            if result:
                last_code = result.data.decode("utf-8")
                x, y, w, h = result.rect
                cv2.rectangle(imr, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(imr, last_code, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)
                print(f"Result = {last_code} & Mean Value: {mean_value}")
        
        # FPS Counter
        e2 = cv2.getTickCount()
        t = (e2 - e1) / cv2.getTickFrequency()
        fps = int(1 / t) if t > 0 else 0
        
        cv2.rectangle(imr, (0, 0), (110, 14), (0, 0, 0), -1)
        cv2.putText(imr, f"{t:.3f}s {fps}fps", (1, 10),cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 250, 0), 1)

        cv2.imshow("Original", frame)
        cv2.imshow(window_name, imr)
        key = cv2.waitKey(1)

        if key in [ord('q'), ord('Q'), 27]:
            filename = f"datamatrix{frame_number:03d}.jpg"
            cv2.imwrite(filename, frame)
            print("Saved frame to", filename)
            break

        frame_number += 1

    # Cleanup
    if decode_proc and decode_proc.is_alive():
        decode_proc.terminate()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        cap = cv2.VideoCapture(1)
        # cap = cv2.VideoCapture(0)
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
    
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, 150) 

    data_matrix_demo(cap)
