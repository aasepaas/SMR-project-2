import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"  # OpenCV warnings uitschakelen

import time
import datetime
import logging
import threading

import cv2
from cv2.typing import MatLike
from pyzbar.pyzbar import decode as qr_decoder

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend - no tkinter/GUI issues

# Private imports
from roi_auto_detector import ROIAutoDetector
from datamatrix_decoder import DataMatrixDecoder
from profile_setup import standard_profile, wallet_profile, giftbox_profile, barcode_profile, ScanProfile

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
#  Camera Scanner
# =====================================================================
class CameraScanner:
    # =====================================================================
    #  Initialization
    # =====================================================================
    def __init__(self, decoder: DataMatrixDecoder, detector: ROIAutoDetector, profile: ScanProfile = standard_profile, debug: bool = False) -> None: 
        self.camera_lock = threading.Lock()
        self.DEBUG = debug
        self.running = True
        self.switch = False        
        self.Detected_all = False
        self.datamatrixes = []  # Store detected datamatrix codes
        self.request_roi_recalc = False
        
        self.profile = profile
        self.rois = profile.rois
               
        # Open camera
        self.cap = cv2.VideoCapture(self.profile.camera_index) 
        if not self.cap.isOpened():
            logger.error("Cannot initialize video capture")
            raise ValueError("Try a different camera_index")

        self.__configure_camera()
        
        self.detector = detector
        self.dm_decoder = decoder
        self.last_code: str = ""
        self.last_code_time = 0
        
        # ROI cycling for multi-ROI profiles
        self.current_roi_index = 0
        # self.roi_detection_times = {}  # Track detection time per ROI index
        self.roi_transition_time = 0  # Track when ROI was last changed
        
        # Triple validation per ROI
        self.current_roi_consecutive_code = None  # Track current consecutive code for this ROI
        self.current_roi_consecutive_count = 0    # Count consecutive detections of same code


    
    def __retrieve_rois(self) -> list[tuple[int, int, int, int]]:
        """Return a new list of ROIs."""
        results = []
        while True:
            # Warm up: discard a few frames from the capture to stabilise exposure/focus
            for _ in range(5):
                ret_skip, frame_skip = self.cap.read()
                if not ret_skip:
                    break
                frame = frame_skip
                time.sleep(0.01)


            if self.DEBUG:
                if results == []:
                    print("In capture loop, waiting for user input...")
                    try:
                        results = self.detector.capture_loop(frame)
                    except Exception as e:
                        logger.error(f"ROI detector capture_loop failed: {e}")
                        results = []
                        break
                elif results != []:
                    print(f"{len(results)} ROI's detected, exiting capture loop.")
                    cv2.destroyAllWindows()
                    break
            else:
                try:
                    results = self.detector.run(frame)
                except Exception as e:
                    logger.error(f"ROI detector run() failed: {e}")
                    results = []
                cv2.destroyAllWindows()
                break
        print(f"{results = }")
        return results

    
    # =====================================================================
    #  Run
    # =====================================================================
    def run(self) -> None:
        print("\nW = Wallet profile | G = Giftbox profile | B = Barcode Profile | Q = Stop frame | ESC = quit")
        print("f/g = Focus | e/r = Exposure | b/n = Brightness | SPACE = Next ROI\n")
        
        # =============================================================
        # Main loop
        # =============================================================
        try:
            while self.running:
                try:
                    ret, frame = self.cap.read()
                except cv2.error as e:
                    logger.error(f"OpenCV error during capture.read(): {e}")
                    # Attempt to recover by reinitializing the capture
                    with self.camera_lock:
                        try:
                            idx = self.profile.camera_index
                            try:
                                self.cap.release()
                            except Exception:
                                pass
                            time.sleep(0.2)
                            try:
                                self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                            except Exception:
                                self.cap = cv2.VideoCapture(idx)

                            start = time.time()
                            while not self.cap.isOpened() and (time.time() - start) < 3.0:
                                time.sleep(0.1)

                            if not self.cap.isOpened():
                                logger.error(f"Reopened camera index {idx} failed")
                                break

                            # Apply profile settings and warm up
                            try:
                                self.__configure_camera()
                            except Exception:
                                pass
                            self.__warmup_camera(frames=15)
                            continue
                        except Exception as e2:
                            logger.error(f"Failed to reinitialize camera after cv2.error: {e2}")
                            break
                
                if self.rois:                
                    self.__draw_rois(frame)
                    ROI_frame = self.__process_frame(frame) 

                    # Expire stored code
                    self.__expire_code_if_needed()

                    # Async decode
                    decoded = self.__decode_roi(ROI_frame) 
                    if decoded:
                        if not self.Detected_all: 
                            self.__update_code(decoded)
                else:
                    ROI_frame = None
                    
                # Display frames
                if self.DEBUG:
                    if frame is not None:
                        self.__show_roi_index(frame) 
                        cv2.imshow("Camera", frame)
                    if ROI_frame is not None: 
                        roi_bgr = cv2.cvtColor(ROI_frame.astype("uint8"), cv2.COLOR_GRAY2BGR) 
                        cv2.imshow("ROI", roi_bgr)
                            
                key = cv2.waitKey(1) & 0xFF
                # key = cv2.waitKey(1)
                # if key != -1:
                #     key &= 0xFF
                    
                if key == ord('W'):
                    self.switch_profile(wallet_profile)
                    
                elif key == ord('G'):
                    self.switch_profile(giftbox_profile)
                    # Request ROI recalculation to be performed inside scanner thread
                    self.request_roi_recalc = True
                    
                elif key == ord('B'):
                    self.switch_profile(barcode_profile)
                    
                elif key == ord(' '):
                    self.datamatrixes.append("")    
                    self.__next_roi()
                elif key == ord('f'):
                    self.__adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, -1)
                elif key == ord('g'):
                    self.__adjust_camera_setting('focus', cv2.CAP_PROP_FOCUS, +1)
                elif key == ord('e'):
                    self.__adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, -1)
                elif key == ord('r'):
                    self.__adjust_camera_setting('exposure', cv2.CAP_PROP_EXPOSURE, +1)
                elif key == ord('b'):
                    self.__adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, -1)
                elif key == ord('n'):
                    self.__adjust_camera_setting('brightness', cv2.CAP_PROP_BRIGHTNESS, +1)
                          
                # If a ROI recalculation was requested by switch_profile(), do it here
                if getattr(self, 'request_roi_recalc', False):
                    try:
                        time.sleep(0.5)  # small delay for camera to stabilise
                        rois = self.__retrieve_rois()
                        if rois:
                            self.rois = rois
                            logger.info(f"Assigned {len(rois)} ROIs from auto-detection for profile {self.profile.name}")
                        else:
                            logger.warning("Auto ROI detection returned no ROIs; keeping profile defaults.")
                    except Exception as e:
                        logger.error(f"Auto ROI detection failed in scanner thread: {e}")
                    finally:
                        try:
                            cv2.destroyAllWindows()
                        except Exception:
                            pass
                    self.request_roi_recalc = False
                    
        finally:
            self.__cleanup()
        
    def __show_roi_index(self, frame) -> None:    
        # Show current ROI index if multi-ROI profile
        if len(self.rois) > 1:
            roi_text = f"ROI {self.current_roi_index + 1}/{len(self.rois)}"
            cv2.putText(frame, roi_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    # =====================================================================
    #  Camera settings
    # =====================================================================
    def __cap_set(self, prop: int, value: float) -> None:
        """Helper: safely set a camera property."""
        
        self.cap.set(prop, value)
    
    def __configure_camera(self) -> None: 
        """ Apply all camera settings from the profile (single source of truth."""

        # Resolution and autofocus (common to all profiles)
        self.__cap_set(cv2.CAP_PROP_FRAME_WIDTH, 1280) # 640
        self.__cap_set(cv2.CAP_PROP_FRAME_HEIGHT, 720) # 480

        if self.profile.focus is not None:
            self.__cap_set(cv2.CAP_PROP_AUTOFOCUS, 0)  # Turn off auto focus
            self.__cap_set(cv2.CAP_PROP_FOCUS, self.profile.focus)
        else:   
            self.__cap_set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Turn on auto focus
            
        if self.profile.exposure is not None:
            self.__cap_set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Turn off auto exposure
            self.__cap_set(cv2.CAP_PROP_EXPOSURE, self.profile.exposure)    
        else:
            self.__cap_set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)  # Turn on auto exposure
            
        if self.profile.brightness is not None:
            self.__cap_set(cv2.CAP_PROP_BRIGHTNESS, self.profile.brightness)
        else:
            self.__cap_set(cv2.CAP_PROP_BRIGHTNESS, 100)  # Default brightness   
                    
    def __adjust_camera_setting(self, attr_name, cap_prop, delta) -> None:
        """Adjust a camera setting by delta and persist to profile."""
        value = getattr(self.profile, attr_name, None)
        if value is not None and self.cap is not None:
            value += delta
            setattr(self.profile, attr_name, value)
            self.cap.set(cap_prop, value)
            logger.info(f"{attr_name.capitalize()} {'omhoog' if delta>0 else 'omlaag'} → {value}")

    def __warmup_camera(self, frames=30):
        """Gooi de eerste frames weg zodat exposure/focus kan stabiliseren"""
        print(f"Warming up camera ({frames} frames)...")
        for _ in range(frames):
            ret, _ = self.cap.read()
            if not ret:
                break

    def __roi_frame_size(self, h,w, roi_box):
        top, bottom, left, right = roi_box
        # Clip bounds
        top = max(0, min(top, h-1))
        bottom = max(top+1, min(bottom, h))
        left = max(0, min(left, w-1))
        right = max(left+1, min(right, w-1))
        return top, bottom, left, right
    
    def __draw_rois(self, frame) -> None:
        """Read frame, clip ROI bounds, draw all ROIs, highlight current ROI, and preprocess."""
        with self.camera_lock:

            h, w = frame.shape[:2] 
           
            # Draw all ROIs in red
            for i, roi_box in enumerate(self.rois): 
                top, bottom, left, right = self.__roi_frame_size(h,w, roi_box)
                
                color = (0, 255, 0) if i == self.current_roi_index else (0, 0, 255) 
                thickness = 3 if i == self.current_roi_index else 2 
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
            
    def __process_frame(self, frame: MatLike) -> MatLike:
        """Extract and convert current ROI to grayscale."""
        top, bottom, left, right = self.__roi_frame_size(frame.shape[0], frame.shape[1], self.rois[self.current_roi_index % len(self.rois)])
        roi = frame[top:bottom, left:right]
        gray_roi = cv2.cvtColor(roi.astype("uint8"), cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray_roi, (0,0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        # Stretch contrast: lichtste pixel -> 255, donkerste pixel -> 0
        norm = cv2.normalize(resized, resized, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        if self.profile.scan_type == "barcode":
            # Additional preprocessing for DataMatrix codes
            norm = cv2.rotate(norm, cv2.ROTATE_90_COUNTERCLOCKWISE)
            # contrast verbeteren (verscherpen)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            norm  = clahe.apply(norm)
            
        return norm

    def __next_roi(self) -> None:
        """Advance to next ROI in the profile."""
        if len(self.rois) > 1:
            self.current_roi_index = (self.current_roi_index + 1) % len(self.rois)
             
            time.sleep(0.05)  # Reduced from 0.2 for faster cycling
            
            # Clear the last code and flush decoder queues
            self.last_code = ""
            self.last_code_time = 0
            self.roi_transition_time = time.time()  # Record transition time
            
            # Reset triple validation counters for new ROI
            self.current_roi_consecutive_code = None
            self.current_roi_consecutive_count = 0
            
            if self.dm_decoder is not None:
                self.dm_decoder.flush_results()
                self.dm_decoder.flush_input()
                
            logger.info(f"Advanced to ROI {self.current_roi_index + 1:>2}/{len(self.rois)}")
                    
        else:
            logger.info("Single ROI profile - cannot advance")

    # =====================================================================
    #  Change profile (and camera if needed)
    # =====================================================================            
    def switch_profile(self, new_profile: ScanProfile) -> None:
        """Look up a profile by name and switch to it."""
        
        self.switch = True        
        # Only switch camera hardware if index changed
        if self.profile.camera_index != new_profile.camera_index:
            self.__switch_camera(new_profile.camera_index)
            
        self.profile = new_profile
        # self.rois = self.profile.rois # Reset ROIS

        # Apply all profile settings (including ROI) in one place
        self.__configure_camera()

        # Log the change
        self.__log_profile_settings()
        
        # Reset flags and counters
        self.current_roi_index = 0
        self.current_roi_consecutive_code = None
        self.current_roi_consecutive_count = 0
        self.Detected_all = False 
        self.switch = False        

        # Flush decoder queues after camera hardware switch
        if self.dm_decoder is not None:
            try:
                self.dm_decoder.flush_results()
                self.dm_decoder.flush_input()
            except Exception:
                pass

        # If GiftBox (or similar) profile selected, request ROI recalculation
        try:
            profile_name = getattr(self.profile, 'name', '').lower()
            if self.profile is giftbox_profile or 'gift' in profile_name:
                # do not run GUI/ROI detection here (may be called from another thread)
                self.request_roi_recalc = True
            else:
                self.rois = self.profile.rois
        except Exception:
            pass

        
    def __switch_camera(self, new_index: int):
        """Safely release old camera and open a new one by index."""
        with self.camera_lock:
            try:
                self.cap.release()
            except Exception:
                pass
            time.sleep(0.3)
            

            # Try a set of backends to open the device, giving diagnostic logs
            backends = [getattr(cv2, 'CAP_DSHOW', None), getattr(cv2, 'CAP_MSMF', None), None]
            opened = False
            last_error = None
            for backend in backends:
                try:
                    if backend is not None:
                        logger.info(f"Attempting to open camera {new_index} with backend {backend}")
                        cap = cv2.VideoCapture(new_index, backend)
                    else:
                        logger.info(f"Attempting to open camera {new_index} with default backend")
                        cap = cv2.VideoCapture(new_index)

                    # wait briefly until opened
                    start = time.time()
                    while not cap.isOpened() and (time.time() - start) < 2.0:
                        time.sleep(0.1)

                    if not cap.isOpened():
                        logger.warning(f"Backend {backend} did not open camera {new_index}")
                        try:
                            cap.release()
                        except Exception:
                            pass
                        continue

                    # Apply temporary safe settings then try reading a few frames
                    self.cap = cap
                    try:
                        self.__configure_camera()
                    except Exception:
                        pass

                    got_frame = False
                    for attempt in range(12):
                        ret, test_frame = self.cap.read()
                        logger.debug(f"Test read attempt {attempt+1}: ret={ret}, frame_valid={test_frame is not None and getattr(test_frame,'size',0)>0}")
                        if ret and test_frame is not None and getattr(test_frame, 'size', 0) > 0:
                            got_frame = True
                            logger.info(f"Camera {new_index} opened successfully with backend {backend}; frame size={test_frame.shape if hasattr(test_frame,'shape') else 'unknown'}")
                            break
                        time.sleep(0.05)

                    if not got_frame:
                        logger.warning(f"Opened camera {new_index} with backend {backend} but no valid frames received")
                        try:
                            self.cap.release()
                        except Exception:
                            pass
                        continue

                    opened = True
                    break

                except Exception as e:
                    last_error = e
                    logger.exception(f"Exception while opening camera {new_index} with backend {backend}: {e}")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    continue

            if not opened:
                logger.error(f"Cannot open camera index {new_index}; last error: {last_error}")
                raise NotImplementedError

            # Final configure and longer warmup for stability
            try:
                self.__configure_camera()
            except Exception:
                pass
            self.__warmup_camera(frames=5)

    def __log_profile_settings(self) -> None: 
        """
            Prints the current profile settings to the console.
            Name, type, index, focus, exposure, brightness.
        """
        # Log the change
        print("\n================================")
        print(f"[PROFILE] Switched to {self.profile.name} ({self.profile.scan_type})")
        print(f" Index      → {self.profile.camera_index}")
        print(f" Focus      → {self.profile.focus}")
        print(f" Exposure   → {self.profile.exposure}")
        print(f" Brightness → {self.profile.brightness}")
        print("================================\n")
                    
    # ==============================================================
    # Decoders (per profile)
    # ==============================================================
    def __decode_roi(self, ROI_frame):
        # --- DataMatrix profiles ---
        if self.profile.scan_type == "datamatrix":
            # Only feed frames to decoder if we've been on this ROI for >100ms
            if time.time() - self.roi_transition_time > 0.1:
                self.dm_decoder.dm_decoder_async(ROI_frame) 
            
            result = self.dm_decoder.get_result()
            str_result = str(result.data.decode("utf-8")) if result else ""
            return str_result
        
        # --- Barcode profiles ---
        elif self.profile.scan_type == "barcode":
            rotated_90_clockwise = cv2.rotate(ROI_frame, cv2.ROTATE_90_CLOCKWISE)
            results = qr_decoder(rotated_90_clockwise) 
            str_result = str(results[0].data.decode("utf-8")) if results else ""
            return str_result

    def __update_code(self, code: str) -> None:
        current_time = time.time()
        
        # ==================================================
        # Check new code
        # ==================================================           
        # last_detection_time = self.roi_detection_times.get(self.current_roi_index, 0)
        
        # Same code as before: increments counter; Different code detected: resets counter
        if code == self.current_roi_consecutive_code: 
            self.current_roi_consecutive_count += 1 
        else: 
            self.current_roi_consecutive_code = code
            self.current_roi_consecutive_count = 1
        
        # ==================================================
        # Execute when 3 times the same code
        # ==================================================           
        if self.current_roi_consecutive_count >= 3 and (current_time - self.roi_transition_time > 0.3): #! Change this time if needed 
            self.last_code = code
            self.last_code_time = current_time
            # Record detection time for this ROI
            # self.roi_detection_times[self.current_roi_index] = current_time
            
            # Log with ROI info if multi-ROI profile
            if len(self.rois) > 1:
                logger.info(f"DECODE [ROI {self.current_roi_index + 1:>2}/{len(self.rois)}] = {code}")
                self.datamatrixes.append(code)
                
                # Auto-advance to next ROI after successful decode
                if len(self.rois) == (self.current_roi_index + 1):
                    print("All Detected")
                    self.Detected_all = True
                    self.rois = self.profile.rois # Reset ROIS
                    self.current_roi_index = 0
                else:
                    self.__next_roi()

            else:
                logger.info(f"DECODE = {code}")
                self.datamatrixes.append(code)
                
            # Reset triple validation for next code
            self.current_roi_consecutive_code = None
            self.current_roi_consecutive_count = 0

    def __expire_code_if_needed(self) -> None:
        """ Clear `last_code` when it has exceeded `profile.data_timeout`. """
        if self.last_code:
            elapsed = time.time() - self.last_code_time
            if elapsed > (self.profile.data_timeout or 0):
                logger.info(f"Code expired: {self.last_code}")
                self.last_code = ""

    # Bastiaan waarom heb ik deze methode?
    def update_state(self, state: str) -> str:
        if (self.state != state):
            logger.info(f"State changed to: {state}")
            self.previous_state = self.state
            self.state = state
        return self.state
    
    # Gebruik deze methode voor het ophalen van de laatste code   
    def get_code(self) -> list[str]:
        if self.datamatrixes != []:
            return self.datamatrixes
        else:
            raise NotImplementedError("No code available")
    
    # =====================================================================
    #  Shutdown
    # =====================================================================
    def exit_loop(self) -> None:
        self.running = False
        
    def __cleanup(self) -> None:
        print("Stop Scanner file")
        # Stop decoder worker 
        if self.dm_decoder:
            self.dm_decoder.stop()
            # self.dm_decoder = None
            
        # Close camera and all windows
        self.cap.release()
        cv2.destroyAllWindows()
