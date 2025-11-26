import cv2
import numpy as np
from pylibdmtx.pylibdmtx import decode
from ultralytics import YOLO
import threading
import time

# ------------ Globale variabelen voor threading ---------------
decode_result = None
decode_lock = threading.Lock()
last_decode_time = 0


def decode_thread(image_roi):
    """Decode DataMatrix in aparte thread"""
    global decode_result
    try:
        results = decode(image_roi)
        with decode_lock:
            decode_result = results
    except Exception as e:
        print("Decode error:", e)
        with decode_lock:
            decode_result = None


# ------------ MAIN PROGRAMMA: YOLO + DATAMATRIX DECODER ----------
def main():
    global last_decode_time

    # ---- YOLO model laden ----
    model = YOLO(r'C:\Users\aashi\Downloads\train7\weights\best.pt')

    # ---- Camera ----
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

    if not cap.isOpened():
        print("Kan camera niet openen!")
        return

    window_name = "YOLO + DataMatrix Decode"
    last_code = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # ---- YOLO detecteert objecten ----
        results = model(frame, verbose=False)
        annotated = results[0].plot()

        # ---- Check of YOLO DataMatrix herkent ----
        for box in results[0].boxes:
            cls = int(box.cls[0])
            name = results[0].names[cls]

            if name.lower() == "datamatrix":
                # Veilig uitlezen als Python-int
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # ---- ROI VERGROTING ----
                margin = 20
                xr1 = max(0, x1 - margin)
                yr1 = max(0, y1 - margin)
                xr2 = min(frame.shape[1], x2 + margin)
                yr2 = min(frame.shape[0], y2 + margin)

                # ROI
                roi = frame[yr1:yr2, xr1:xr2]

                # Decode max 1x per 0.3s
                if time.time() - last_decode_time > 0.3:
                    threading.Thread(target=decode_thread, args=(roi.copy(),), daemon=True).start()
                    last_decode_time = time.time()

                # Teken originele YOLO-box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # ------ Decoder resultaat tonen ------
        with decode_lock:
            if decode_result:
                result = decode_result[0]
                last_code = result.data.decode("utf-8")

                print("data matrix code: ", last_code)

                # Zet tekst bovenaan het scherm
                cv2.putText(annotated, f"DataMatrix: {last_code}",
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.9, (0, 255, 0), 2)

        # ---- Beeld tonen ----
        cv2.imshow(window_name, annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# ---- Start programma ----
if __name__ == "__main__":
    main()
