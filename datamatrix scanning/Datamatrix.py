import cv2
import time
import sys
from multiprocessing import Process, Queue
from pylibdmtx.pylibdmtx import decode


class DataMatrixDecoder:
    """Separate decoder using multiprocessing."""

    def __init__(self):
        self.result_queue = Queue()
        self.decode_proc = None
        self.last_decode_time = 0

    def start_decode(self, frame):
        """Starts a decode process every 0.1s."""
        if time.time() - self.last_decode_time > 0.1:
            if self.decode_proc is None or not self.decode_proc.is_alive():
                self.decode_proc = Process(target=self.decode_worker,
                                           args=(frame.copy(), self.result_queue))
                self.decode_proc.start()
                self.last_decode_time = time.time()

    @staticmethod
    def decode_worker(frame, queue):
        """Worker process for decoding."""
        try:
            results = decode(frame)
            queue.put(results[0] if results else None)
        except Exception as e:
            print("Decode error:", e)
            queue.put(None)

    def get_result(self):
        """Check if the decoder returned something."""
        if not self.result_queue.empty():
            return self.result_queue.get()
        return None

    def stop(self):
        if self.decode_proc and self.decode_proc.is_alive():
            self.decode_proc.terminate()


class CameraScanner:
    """Main class to handle video capturing, ROI selection, and displaying."""

    def __init__(self, cam_index=0):
        self.cap = cv2.VideoCapture(cam_index)
        if not self.cap.isOpened():
            print("Cannot initialize video capture")
            sys.exit(-1)

        # Set resolution and focus
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        self.cap.set(cv2.CAP_PROP_FOCUS, 175)

        self.decoder = DataMatrixDecoder()

        # ROI area
        self.top = 550
        self.bottom = 650
        self.left = 800
        self.right = 900

        self.frame_number = 0

    def process_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None, None

        # Draw ROI rectangle
        cv2.rectangle(frame, (self.left, self.top), (self.right, self.bottom), (0, 0, 255), 2)

        # Extract ROI
        roi = frame[self.top:self.bottom, self.left:self.right]
        return frame, roi, True

    def run(self):
        window_name = "Datamatrix Scanner"

        while True:
            e1 = cv2.getTickCount()
            frame, roi, ok = self.process_frame()

            if not ok:
                break

            # Start async decode
            self.decoder.start_decode(roi)

            # Check for results
            result = self.decoder.get_result()
            if result:
                self.code = result.data.decode("utf-8")
                print("Result =", self.code)

            # FPS display
            e2 = cv2.getTickCount()
            t = (e2 - e1) / cv2.getTickFrequency()
            fps = int(1 / t) if t > 0 else 0

            cv2.putText(frame, f"{t:.3f}s {fps}fps", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Show windows
            cv2.imshow("Original", frame)
            cv2.imshow(window_name, roi)

            key = cv2.waitKey(1)
            if key in [ord('q'), ord('Q'), 27]:
                break

            self.frame_number += 1

        self.cleanup()

    def cleanup(self):
        self.decoder.stop()
        self.cap.release()
        cv2.destroyAllWindows()

    def get_datamatrix_code(self):
        return self.code

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cam_input = int(sys.argv[1])
        try:
            cam_input = int(cam_input)
        except:
            pass
        scanner = CameraScanner(cam_input)
    else:
        scanner = CameraScanner(0)

    scanner.run()
