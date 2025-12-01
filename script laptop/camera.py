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
        self.cam_index = cam_index
        self.cap = None
        self.decoder = DataMatrixDecoder()

        # ROI
        self.top = 550
        self.bottom = 650
        self.left = 800
        self.right = 900

        self.code = 0

    def open_camera(self):

        self.cap = cv2.VideoCapture(self.cam_index)


        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
            print("Cannot initialize video capture on external camera back to laptop cam")

        # Settings
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        self.cap.set(cv2.CAP_PROP_FOCUS, 175)
        return True

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
        if not self.open_camera():
            return

        window_name = "Datamatrix Scanner"
        self.code = None

        frame_count = 0

        while True:
            e1 = cv2.getTickCount()
            frame, roi, ok = self.process_frame()
            if not ok:
                break

            self.decoder.start_decode(roi)

            result = self.decoder.get_result()
            if result:
                self.code = result.data.decode("utf-8")
                print("Result =", self.code)
                break

            # FPS
            e2 = cv2.getTickCount()
            t = (e2 - e1) / cv2.getTickFrequency()
            fps = int(1 / t) if t > 0 else 0
            cv2.putText(frame, f"{t:.3f}s {fps}fps", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            cv2.imshow("Original", frame)
            cv2.imshow(window_name, roi)

            key = cv2.waitKey(1)
            if key in [ord('q'), ord('Q'), 27]:
                break

            frame_count += 1
            if frame_count > 200:
                break

        self.cleanup()

    def cleanup(self):
        self.decoder.stop()
        if self.cap:
            self.cap.release()
            self.cap = None

        cv2.destroyAllWindows()

    def get_datamatrix_code(self):
        if self.code is None:
            return 0
        return self.code

    def close(self):
        self.decoder.stop()
        self.cap.release()
        cv2.destroyAllWindows()
