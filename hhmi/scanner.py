import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"  # OpenCV warnings uitschakelen

import time
import datetime
import logging
import sys
from multiprocessing import Process, Queue
import threading

import cv2
from cv2.typing import MatLike
from pyzbar.pyzbar import decode as qr_decoder
from pylibdmtx.pylibdmtx import decode as dm_decoder
from pylibdmtx.pylibdmtx import Decoded

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
    """Stores ROI(s) + focus + exposure + brightness settings for a scan target."""
    def __init__(self, name, camera_index, roi, focus, exposure=None, brightness=None, data_timeout=2.0, type="datamatrix"):
        self.name = name
        self.camera_index = camera_index
        # Support both single ROI (tuple) and multiple ROIs (list of tuples)
        self.roi = roi if isinstance(roi, list) else [roi]
        self.focus = int(focus)
        self.exposure = int(exposure) if exposure is not None else None
        self.brightness = int(brightness) if brightness is not None else None
        self.data_timeout = data_timeout
        self.type = type # "datamatrix" or "barcode"

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
            except Exception:
                continue
            
            if frame is None:
                break
            
            try:
                results = dm_decoder(frame)
                if not self.result_queue.full():
                    self.result_queue.put(results[0] if results else None)
            except Exception as e:
                logger.error(f"Decoder error: {e}")
                if not self.result_queue.full():
                    self.result_queue.put(None)

    def dm_decoder_async(self, frame) -> None:
        if self.input_queue.empty():
            try:
                self.input_queue.put(frame, timeout=0.01)
            except Exception:
                pass

    def get_result(self) -> Decoded | None:
        try:
            return self.result_queue.get_nowait()
        except Exception:
            return None

    def flush_results(self) -> None:
        """Clear any pending results from the queue."""
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except Exception:
                break

    def flush_input(self) -> None:
        """Clear any pending input frames from the queue."""
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except Exception:
                break

    def stop(self) -> None:
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
    # =====================================================================
    #  Initialization
    # =====================================================================
    def __init__(self, profiles: dict[str, ScanProfile]) -> None: 
        self.camera_lock = threading.Lock()
        self.running = True
        self.profiles = profiles
        
        # Use the first profile as the starting profile (raise if empty)
        try:
            self.profile = next(iter(profiles.values()))
        except StopIteration:
            raise ValueError("profiles must contain at least one ScanProfile")
        assert self.profile is not None
        
        # Open camera
        self.cap = cv2.VideoCapture(self.profile.camera_index) 
        if not self.cap.isOpened():
            logger.error("Cannot initialize video capture")
            sys.exit(-1)

        self.__configure_camera(self.profile)
        
        # ROI cycling for multi-ROI profiles
        self.current_roi_index = 0
        self.top, self.bottom, self.left, self.right = self.profile.roi[0]
        
        self.dm_decoder = None #DataMatrixDecoder()
        self.last_code = None
        self.last_code_time = 0
        self.roi_detection_times = {}  # Track detection time per ROI index
        self.roi_transition_time = 0  # Track when ROI was last changed

    # =====================================================================
    #  Runtime loop
    # =====================================================================
    def run(self) -> None:
        print("W = Wallet profile | G = Giftbox profile | B = Barcode Profile | Q/ESC = quit")
        print("f/g = Focus | e/r = Exposure | b/n = Brightness | SPACE = Next ROI\n")
        ShowDebugFrame = True

        try:
            while self.running:
                start_time = time.time()
                frame, roi, ok = self.__process_frame()
                if not ok:
                    break
                
                # Async decode
                decoded = self.__decode_roi(roi)
                self.__update_code(decoded)

                # Display frames
                if ShowDebugFrame:
                    if frame is not None:
                        self.__show_fps(frame, start_time)
                        self.__show_roi_index(frame)
                        cv2.imshow("Camera", frame)
                if roi is not None:
                    roi_bgr = cv2.cvtColor(roi.astype("uint8"), cv2.COLOR_GRAY2BGR)
                    cv2.imshow("ROI", roi_bgr)

                key_actions = {
                    # ord('q'): lambda: self.exit_loop(),
                    # 27: lambda: self.exit_loop(),  # ESC
                    ord('W'): lambda: self.switch_profile('wallet'),
                    ord('G'): lambda: self.switch_profile('giftbox'),
                    ord('B'): lambda: self.switch_profile('barcode'),
                    ord(' '): lambda: self.__next_roi(),
                    ord('f'): lambda: self.__adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, -1),
                    ord('g'): lambda: self.__adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, +1),
                    ord('e'): lambda: self.__adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, -1),
                    ord('r'): lambda: self.__adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, +1),
                    ord('b'): lambda: self.__adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, -1),
                    ord('n'): lambda: self.__adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, +1),
                }
                
                # key = cv2.waitKey(1) & 0xFF
                key = cv2.waitKey(1)
                if key != -1:
                    key &= 0xFF

                if key in key_actions:
                    key_actions[key]()

        finally:
            self.__cleanup()

    def __show_fps(self, frame, start_time) -> None:
        fps = int(1 / (time.time() - start_time))
        cv2.putText(frame, f"{fps} fps", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
    def __show_roi_index(self, frame) -> None:    
        # Show current ROI index if multi-ROI profile
        if len(self.profile.roi) > 1:
            roi_text = f"ROI {self.current_roi_index + 1}/{len(self.profile.roi)}"
            cv2.putText(frame, roi_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    # =====================================================================
    #  Camera settings
    # =====================================================================
    def __cap_set(self, prop: int, value: float) -> None:
        """Helper: safely set a camera property."""
        if self.cap is not None:
            self.cap.set(prop, value)
    
    def __configure_camera(self, profile: ScanProfile) -> None: 
        """Apply all camera settings and ROI from the profile (single source of truth)."""
        if self.cap is None:  
            return  

        # Resolution and autofocus (common to all profiles)
        self.__cap_set(cv2.CAP_PROP_FRAME_WIDTH, 1280) # 640
        self.__cap_set(cv2.CAP_PROP_FRAME_HEIGHT, 720) # 480
        self.__cap_set(cv2.CAP_PROP_AUTOFOCUS, 0)

        # Profile-specific settings (focus, exposure, brightness)
        props = {
            cv2.CAP_PROP_FOCUS: profile.focus,
            cv2.CAP_PROP_EXPOSURE: profile.exposure,
            cv2.CAP_PROP_BRIGHTNESS: profile.brightness
        }

        for prop, value in props.items():
            if value is not None:
                if prop == cv2.CAP_PROP_EXPOSURE:
                    self.__cap_set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.__cap_set(prop, value)

        # Reset to first ROI when switching profiles
        self.current_roi_index = 0
        self.top, self.bottom, self.left, self.right = profile.roi[0]

    def __adjust_camera_setting(self, attr_name, cap_prop, delta) -> None:
        """Adjust a camera setting by delta and persist to profile."""
        value = getattr(self.profile, attr_name, None)
        if value is not None and self.cap is not None:
            value += delta
            setattr(self.profile, attr_name, value)
            self.cap.set(cap_prop, value)
            logger.info(f"{attr_name.capitalize()} {'omhoog' if delta>0 else 'omlaag'} → {value}")

    def __process_frame(self) -> tuple[MatLike, MatLike, bool] | tuple[None, None, bool]:
        """Read frame, clip ROI bounds, draw all ROIs, highlight current ROI, and preprocess."""
        with self.camera_lock:
            if not self.cap:
                return None, None, False

            ret, frame = self.cap.read()
            if not ret:
                return None, None, False

            h, w = frame.shape[:2] 

            # Clip current ROI to frame bounds
            self.top = max(0, min(self.top, h-1)) 
            self.bottom = max(self.top+1, min(self.bottom, h)) 
            self.left = max(0, min(self.left, w-1)) 
            self.right = max(self.left+1, min(self.right, w-1))
            
            # Draw all ROIs in red
            for i, roi_box in enumerate(self.profile.roi):
                top, bottom, left, right = roi_box
                # Clip bounds
                top = max(0, min(top, h-1))
                bottom = max(top+1, min(bottom, h))
                left = max(0, min(left, w-1))
                right = max(left+1, min(right, w-1))
                
                color = (0, 255, 0) if i == self.current_roi_index else (0, 0, 255)
                thickness = 3 if i == self.current_roi_index else 2
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
            
            roi = self.__preprocess_frame(frame)
            
            return frame, roi, True

    def __preprocess_frame(self, frame: MatLike) -> MatLike:
        """Extract and convert current ROI to grayscale."""
        roi = frame[self.top:self.bottom, self.left:self.right]
        gray_roi = cv2.cvtColor(roi.astype("uint8"), cv2.COLOR_BGR2GRAY)
        return gray_roi

    def __next_roi(self) -> None:
        """Advance to next ROI in the profile."""
        if len(self.profile.roi) > 1:
            time.sleep(0.05)  # Reduced from 0.2 for faster cycling
            self.current_roi_index = (self.current_roi_index + 1) % len(self.profile.roi)
            self.top, self.bottom, self.left, self.right = self.profile.roi[self.current_roi_index]
            
            # Clear the last code and flush decoder queues
            self.last_code = None
            self.last_code_time = 0
            self.roi_transition_time = time.time()  # Record transition time
            
            if self.dm_decoder is not None:
                self.dm_decoder.flush_results()
                self.dm_decoder.flush_input()
            logger.info(f"Advanced to ROI {self.current_roi_index + 1}/{len(self.profile.roi)}")
        else:
            logger.info("Single ROI profile - cannot advance")

    # =====================================================================
    #  Change profile (and camera if needed)
    # =====================================================================            
    def switch_profile(self, name: str):
        """Look up a profile by name and switch to it."""
        profile = self.profiles.get(name)
        if profile:
            self.__set_profile(profile)
        else:
            print(f"[Controller] Profile '{name}' bestaat niet!")
        
    def __set_profile(self, new_profile: ScanProfile) -> None:
        """Switch to a new profile: handle camera switch, configure, and log."""
        if self.profile == new_profile:
            return
        old_camera_index = self.profile.camera_index if self.profile else None
        self.profile = new_profile

        # Only switch camera hardware if index changed
        if old_camera_index != new_profile.camera_index:
            self.__switch_camera(new_profile.camera_index)

        # Apply all profile settings (including ROI) in one place
        self.__configure_camera(new_profile)

        # Log the change
        self.__log_profile_settings(new_profile)
                
        # if new_profile.type != "datamatrix" and self.dm_decoder is not None:
        #     self.dm_decoder.stop()
        #     self.dm_decoder = None
            
    def __switch_camera(self, new_index: int):
        """Safely release old camera and open a new one by index."""
        with self.camera_lock:
            if self.cap:
                self.cap.release()

            self.cap = cv2.VideoCapture(new_index)
            if not self.cap.isOpened():
                logger.error(f"Cannot open camera index {new_index}")
                self.cap = None
                return

    def __log_profile_settings(self, new_profile: ScanProfile)-> None: 
        """
            Prints the current profile settings to the console.
            Name, type, index, ROI(s), focus, exposure, brightness.
        """
        # Log the change
        print("\n================================")
        print(f"[PROFILE] Switched to {new_profile.name} ({new_profile.type})")
        print(f" Index      → {new_profile.camera_index}")
        if len(new_profile.roi) == 1:
            print(f" ROI        → {new_profile.roi[0]}")
        else:
            print(f" ROI's      → {len(new_profile.roi)} regions")
            for i, roi in enumerate(new_profile.roi):
                print(f"   [{i+1}] {roi}")
        print(f" Focus      → {new_profile.focus}")
        print(f" Exposure   → {new_profile.exposure}")
        print(f" Brightness → {new_profile.brightness}")
        print("================================\n")
                    
    # ==============================================================
    # Decoders (per profile)
    # ==============================================================
    def __decode_roi(self, roi):
        # --- DataMatrix profiles ---
        if self.profile.type == "datamatrix":
            if self.dm_decoder is None:
                self.dm_decoder = DataMatrixDecoder()
            
            # Only feed frames to decoder if we've been on this ROI for >100ms
            # Reduced from 0.3s for faster processing
            if time.time() - self.roi_transition_time > 0.1:
                self.dm_decoder.dm_decoder_async(roi)
            
            result = self.dm_decoder.get_result()
            if result:
                try:
                    return result.data.decode("utf-8")
                except Exception:
                    return None
            return None

        # --- Barcode profiles ---
        elif self.profile.type == "barcode":
            results = qr_decoder(roi)
            if results:
                try:
                    return results[0].data.decode("utf-8")
                except Exception:
                    return None
            return None

    def __update_code(self, code) -> None:
        current_time = time.time()
        
        if code:
            # Get last detection time for this specific ROI (default to very old time)
            last_detection_time = self.roi_detection_times.get(self.current_roi_index, 0)
            
            # Reduced cooldown from 0.5s to 0.2s and transition buffer from 0.4s to 0.15s
            if (current_time - last_detection_time > 0.2 and 
                current_time - self.roi_transition_time > 0.3): #! Change this time if needed 
                self.last_code: str | None = str(code)
                self.last_code_time = current_time
                # Record detection time for this ROI
                self.roi_detection_times[self.current_roi_index] = current_time
                
                # Log with ROI info if multi-ROI profile
                if len(self.profile.roi) > 1:
                    logger.info(f"DECODE [ROI {self.current_roi_index + 1}/{len(self.profile.roi)}] = {code}")
                    # Auto-advance to next ROI after successful decode
                    self.__next_roi()
                else:
                    logger.info(f"DECODE = {code}")

        # Remove outdated code
        if self.last_code and current_time - self.last_code_time > self.profile.data_timeout:
            print("Code expired:", self.last_code)
            self.last_code = None

    # Bastiaan waarom heb ik deze methode?
    def update_state(self, state: str) -> str:
        if (self.state != state):
            logger.info(f"State changed to: {state}")
            self.previous_state = self.state
            self.state = state
        return self.state
    
    # Gebruik deze methode voor het ophalen van de laatste code   
    def get_code(self) -> str:
        if self.last_code is not None:
            return self.last_code
        else:
            #raise NotImplementedError("No code available")
            return None

    
    # =====================================================================
    #  Shutdown
    # =====================================================================
    def exit_loop(self) -> None:
        self.running = False
        
    def __cleanup(self) -> None:
        # Stop decoder worker 
        if self.dm_decoder:
            self.dm_decoder.stop()
            self.dm_decoder = None
            
        # Close camera and all windows
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()