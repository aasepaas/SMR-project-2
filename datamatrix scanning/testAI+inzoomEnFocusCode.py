import cv2
import numpy as np
from pylibdmtx.pylibdmtx import decode
from multiprocessing import Process, Queue
from ultralytics import YOLO
import sys
import time


# ---------- Multiprocessing decode functie ----------
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


# ---------- MAIN PROGRAMMA MET YOLO-AI ----------
def data_matrix_demo(cap):

    # YOLO model laden
    model = YOLO(r'C:\Users\\Downloads\train7\weights\best.pt')

    frame_number = 0
    last_code = None
    last_decode_time = 0

    result_queue = Queue()
    decode_proc = None

    window_name = "YOLO + DataMatrix Decode"

    while True:
        e1 = cv2.getTickCount()

        ret, frame = cap.read()
        if not ret:
            break

        # ---- YOLO detectie ----
        results = model(frame, verbose=False)
        annotated = results[0].plot()

        datamatrix_detected = False
        roi = None

        # Zoek DataMatrix objecten
        for box in results[0].boxes:
            cls = int(box.cls[0])
            name = results[0].names[cls]

            if name.lower() == "datamatrix":
                datamatrix_detected = True

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # ROI iets groter maken voor betere decode
                margin = 20
                xr1 = max(0, x1 - margin)
                yr1 = max(0, y1 - margin)
                xr2 = min(frame.shape[1], x2 + margin)
                yr2 = min(frame.shape[0], y2 + margin)

                roi = frame[yr1:yr2, xr1:xr2]

                # Teken YOLO box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # ---- Start decode alleen als YOLO iets ziet ----
        if datamatrix_detected and roi is not None:
            if time.time() - last_decode_time > 0.15:
                if decode_proc is None or not decode_proc.is_alive():
                    decode_proc = Process(target=decode_process, args=(roi.copy(), result_queue))
                    decode_proc.start()
                    last_decode_time = time.time()

        # ---- Check decode resultaat ----
        if not result_queue.empty():
            result = result_queue.get()
            if result:
                last_code = result.data.decode("utf-8")

                print("DataMatrix:", last_code)

                cv2.putText(
                    annotated,
                    f"DataMatrix: {last_code}",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2
                )

        # ---- FPS ----
        e2 = cv2.getTickCount()
        t = (e2 - e1) / cv2.getTickFrequency()
        fps = int(1 / t) if t > 0 else 0

        cv2.putText(annotated, f"{t:.3f}s {fps}fps", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # ---- Beeld tonen ----
        cv2.imshow(window_name, annotated)

        key = cv2.waitKey(1)
        if key in [ord('q'), ord('Q'), 27]:
            filename = f"datamatrix{frame_number:03d}.jpg"
            cv2.imwrite(filename, frame)
            print("Saved frame:", filename)
            break

        frame_number += 1

    # Cleanup
    if decode_proc and decode_proc.is_alive():
        decode_proc.terminate()

    cap.release()
    cv2.destroyAllWindows()


# ---------- Startup ----------
if __name__ == '__main__':
    if len(sys.argv) == 1:
        cap = cv2.VideoCapture(1)
    else:
        cap = cv2.VideoCapture(sys.argv[1])
        if not cap.isOpened():
            cap = cv2.VideoCapture(int(sys.argv[1]))

    if not cap.isOpened():
        print('Cannot initialize video capture')
        sys.exit(-1)

    # Camera instellingen
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, 150)

    data_matrix_demo(cap)
