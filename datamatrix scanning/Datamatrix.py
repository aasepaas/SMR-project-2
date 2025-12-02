import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"  # OpenCV warnings uitschakelen

import time
import datetime
import logging
import sys
from multiprocessing import Process, Queue

import cv2
from cv2.typing import MatLike
from pylibdmtx.pylibdmtx import decode, Decoded

# ====================== Microsecond-safe logging ======================
class MicrosecondFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.datetime.fromtimestamp(record.created)
        return ct.strftime("%H:%M:%S.%f") 

logger = logging.getLogger()
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(MicrosecondFormatter(fmt="%(asctime)s %(message)s"))
logger.addHandler(ch)

# =====================================================================
#  Profile Class
# =====================================================================
class ScanProfile:
    """Stores ROI + focus + exposure + brightness settings for a scan target."""
    def __init__(self, name, roi, focus, exposure=None, brightness=None, data_timeout=2.0):
        self.name = name
        self.roi = roi
        self.focus = int(focus)
        self.exposure = int(exposure) if exposure is not None else None
        self.brightness = int(brightness) if brightness is not None else None
        self.data_timeout = data_timeout

# =====================================================================
#  Data-Matrix Decoder Class
# =====================================================================
class DataMatrixDecoder:
    def __init__(self) -> None:
        self.input_queue = Queue(maxsize=1)
        self.result_queue = Queue(maxsize=1)
        self.proc = Process(target=self.worker)
        self.proc.start()

    def worker(self) -> None:
        while True:
            try:
                frame = self.input_queue.get(timeout=0.1)
            except:
                continue
            
            if frame is None:
                break
            
            try:
                results = decode(frame)
                if not self.result_queue.full():
                    self.result_queue.put(results[0] if results else None)
            except Exception as e:
                logger.error(f"Decoder error: {e}")
                if not self.result_queue.full():
                    self.result_queue.put(None)

    def decode_async(self, frame) -> None:
        if self.input_queue.empty():
            try:
                self.input_queue.put(frame, timeout=0.01)
            except:
                pass

    def get_result(self) -> Decoded | None:
        try:
            return self.result_queue.get_nowait()
        except:
            return None

    def stop(self) -> None:
        """Stoppen van de worker: stuur stop-signaal en beëindig proces."""
        try:
            self.input_queue.put_nowait(None)
        except Exception:
            pass

        proc = self.proc
        if proc is not None:
            proc.join(timeout=1.0)

            if proc.is_alive():
                proc.terminate()

        self.proc = None


# =====================================================================
#  Camera Scanner
# =====================================================================
class CameraScanner:
    def __init__(self, profile: ScanProfile, cam_index: int=0) -> None:
        self.running = True
        self.profile = profile
        self.cap = cv2.VideoCapture(cam_index)
        if not self.cap.isOpened():
            logger.error("Cannot initialize video capture")
            sys.exit(-1)

        self.configure_camera(profile)
        self.decoder = DataMatrixDecoder()
        self.last_code = None
        self.last_code_time = 0

    def set_profile(self, new_profile: ScanProfile) -> None:
        """Set new values for profile and prints them"""
        self.configure_camera(new_profile)
        print("\n================================")
        print(f"[PROFILE] Switched to {new_profile.name}")
        print(f" ROI        → {new_profile.roi}")
        print(f" Focus      → {new_profile.focus}")
        print(f" Exposure   → {new_profile.exposure}")
        print(f" Brightness → {new_profile.brightness}")
        print("================================\n")

    def configure_camera(self, profile: ScanProfile) -> None:
        """Set all camera settings based on the profile."""
        # Basisresolutie en autofocus
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

        # Camera-instellingen afhankelijk van profiel
        props = {
            cv2.CAP_PROP_FOCUS: profile.focus,
            cv2.CAP_PROP_EXPOSURE: profile.exposure,
            cv2.CAP_PROP_BRIGHTNESS: profile.brightness
        }

        for prop, value in props.items():
            if value is not None:
                if prop == cv2.CAP_PROP_EXPOSURE:
                    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.cap.set(prop, value)

        # ROI
        self.top, self.bottom, self.left, self.right = profile.roi

    def preprocess_frame(self, frame: MatLike) -> MatLike:
        roi = frame[self.top:self.bottom, self.left:self.right]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return gray_roi

    def process_frame(self) -> tuple[MatLike, MatLike, bool] | tuple[None, None, bool]:
        ret, frame = self.cap.read()
        if not ret:
            return None, None, False
        
        cv2.rectangle(frame, (self.left, self.top), (self.right, self.bottom), (0, 0, 255), 2)
        gray_roi = self.preprocess_frame(frame)
        
        return frame, gray_roi, True

    def update_code_storage(self, decoded) -> None:
        if decoded:
            code = decoded.data.decode("utf-8")
            self.last_code: str | None = str(code)
            self.last_code_time = time.time()
            logger.info(f"DECODE = {code}")

        # Remove outdated code
        if self.last_code and time.time() - self.last_code_time > self.profile.data_timeout:
            print("Code expired:", self.last_code)
            self.last_code = None

    def adjust_camera_setting(self, attr_name, cap_prop, delta) -> None:
        value = getattr(self.profile, attr_name, None)
        if value is not None:
            value += delta
            setattr(self.profile, attr_name, value)
            self.cap.set(cap_prop, value)
            logger.info(f"{attr_name.capitalize()} {'omhoog' if delta>0 else 'omlaag'} → {value}")

    def show_fps(self, frame, start_time) -> None:
        fps = int(1 / (time.time() - start_time))
        cv2.putText(frame, f"{fps} fps", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    def exit_loop(self) -> None:
        self.running = False

    def get_code(self) -> str:
        if self.last_code is not None:
            return self.last_code
        else:
            pass
    
    def run(self, wallet_profile: ScanProfile, giftbox_profile: ScanProfile) -> None:
        print("W = Wallet profile | G = Giftbox profile | Q/ESC = quit")
        print("f/g = Focus | e/r = Exposure | b/n = Brightness\n")
        ShowDebugFrame = True

        try:
            while self.running:
                start_time = time.time()
                frame, roi, ok = self.process_frame()
                if not ok:
                    break
                
                # Async decode
                self.decoder.decode_async(roi)
                decoded = self.decoder.get_result()
                self.update_code_storage(decoded)

                if ShowDebugFrame:
                    self.show_fps(frame, start_time)
                    cv2.imshow("Camera", frame)
                cv2.imshow("ROI", roi)

                key_actions = {
                    ord('q'): lambda: self.exit_loop(),
                    27: lambda: self.exit_loop(),  # ESC
                    ord('W'): lambda: self.set_profile(wallet_profile),
                    ord('G'): lambda: self.set_profile(giftbox_profile),
                    ord('f'): lambda: self.adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, -1),
                    ord('g'): lambda: self.adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, +1),
                    ord('e'): lambda: self.adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, -1),
                    ord('r'): lambda: self.adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, +1),
                    ord('b'): lambda: self.adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, -1),
                    ord('n'): lambda: self.adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, +1),
                }

                key = cv2.waitKey(1) & 0xFF
                if key in key_actions:
                    key_actions[key]()

        finally:
            self.cleanup()

    def cleanup(self) -> None:
        # Stop decoder worker 
        if self.decoder:
            self.decoder.stop()
            self.decoder = None
            
        # Sluit camera en vensters
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()

# =====================================================================
#  MAIN
# =====================================================================
if __name__ == "__main__":
    
    # Wallet profile
    top1, left1 = 525, 800
    bottom1, right1 = top1 + 100, left1 + 100
    wallet_profile = ScanProfile(
        name="Wallet",
        roi=(top1, bottom1, left1, right1),
        focus=175,
        exposure=-5,
        brightness=100,
        data_timeout=0.5
    )

    # Giftbox profile
    top2, left2 = 300, 800
    bottom2, right2 = top2 + 150, left2 + 150
    giftbox_profile = ScanProfile(
        name="GiftBox",
        roi=(top2, bottom2, left2, right2),
        focus=120,
        exposure=-4,
        brightness=100,
        data_timeout=0.5
    )

    scanner = CameraScanner(wallet_profile, cam_index=0)
    scanner.run(wallet_profile, giftbox_profile)
