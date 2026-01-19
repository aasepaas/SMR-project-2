import math
import os
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"  # OpenCV warnings uitschakelen

import time
import numpy as np
import cv2
from cv2.typing import MatLike

# Private imports
from feed import resize_frame
from roi_auto_detector import ROIAutoDetector
from decoders_zxingcpp import DataMatrixDecoder as DataMatrixDecoder
from profile_setup import standard_profile, wallet_profile, giftbox_profile, ScanProfile

# Debugging
from logging_config import set_up_logger
import logging
logger = logging.getLogger()
set_up_logger()

def nothing(x):
    pass

def make_odd(x: int) -> int:
    x = max(3, int(x))
    return x | 1

# =====================================================================
#  Camera Scanner
# =====================================================================
class CameraScanner:
    # =================================================================
    #  Initialization
    # =================================================================
    def __init__(self, 
                 dm_decoder: DataMatrixDecoder,
                 detector: ROIAutoDetector, 
                 feed_list: list,
                 profile: ScanProfile = standard_profile, 
                 debug: bool = False) -> None: 
        
        # Setting up received parameters
        self.dm_decoder = dm_decoder
        self.detector = detector
        self.feed_list = feed_list
        self.profile: ScanProfile = profile
        self.rois: dict[int, tuple[int, int, int, int]] = profile.rois
        self.DEBUG_show_images: bool = debug

        # Setting up feed activity
        self.streams = [f.openFeed() for f in feed_list]
                
        # Setting up boolean flags 
        self.running: bool = True
        self.detected_all: bool = False
        self.timeout_reached: bool = False
        self.codes_retrieved: bool = False # Has the last full set of codes been retrieved by caller?
        
        # Setting up storage variables
        self.persistent_results: dict[int, str] = {} # Results that stay saved (only reset on profile switch)
        self.code_detected_time: float = time.perf_counter()
        self.profile_switch_time: float = time.perf_counter()
                
        self.threshold_value: int | None = None
        self.adaptive_threshold_values: tuple[int, int] | None = None
        
    def __del__(self) -> None:
        print("Stop Scanner file")
        # Close camera and all windows
        cv2.destroyAllWindows()
        
    def set_active(self, idx: int) -> None:
        for i, f in enumerate(self.feed_list):
            f.isactive = (i == idx)

    def __retrieve_rois(self, frame: MatLike) -> dict[int, tuple[int,int,int,int]]:
        """Uses the auto_ROI_detector() to find ROIs in the given frame
        Args:
            Frame: The image frame to process for ROI detection.
        Returns:
            A dictionary mapping ROI index to ROI box (top, bottom, left, right).
        """
        try:
            rois = self.detector.capture_loop(frame, automatic=True)
            if not rois:
                return {}  # Return dummy ROI on failure
            
            cv2.destroyAllWindows()            
            logger.debug(f"Assigned {len(rois)} ROIs from auto-detection for profile {self.profile.name}")
            return rois

        except Exception as e:
            logger.error(f"Auto ROI detection failed in scanner: {e}")
    
        return {}  # Return dummy ROI on failure
    
    def __show_all_rois(self, rois_input=None, frame: MatLike | None =None, display_vertical=True, window_name="ROI Grid") -> None:
        """Create a grid visualization of ROIs.
        Args:
            rois_input: Dict mapping ROI index to pre-extracted image, or None to extract from frame
            frame: Original frame to extract ROIs from (if rois_input is None)
            display_vertical: If True, fill grid vertically; if False, horizontally
            window_name: Name for the display window
        """
        ordered_keys = list(self.rois.keys())
        
        total = len(ordered_keys)
        if total <= 0:
            return
        
        # Calculate grid dimensions
        cols = min(5, max(1, math.ceil(total / 10)))
        rows = min(10, max(1, math.ceil(total / cols)))
        
        # Determine cell size
        if rois_input is not None:
            target_w, target_h = self._get_size_from_images(rois_input)
        elif frame is not None:
            first_roi = next(iter(self.rois.values()))
            top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], first_roi)
            target_w, target_h = right - left, bottom - top
        else: 
            return
        
        # Create canvas
        canvas = np.zeros((rows * target_h, cols * target_w, 3), dtype=np.uint8)
        
        # Fill grid
        for i, rois_key in enumerate(ordered_keys):
            if i >= (cols * rows):
                break
            
            # Calculate position
            col = i // rows if display_vertical else i  % cols
            row = i  % rows if display_vertical else i // cols 
            y_start, y_end = row * target_h, (row + 1) * target_h
            x_start, x_end = col * target_w, (col + 1) * target_w
            
            # Get or extract image
            if rois_input is not None:
                img = rois_input.get(rois_key)
                if img is None or img.size == 0:
                    continue
                img_bgr = self._convert_to_bgr(img)
                try:
                    img_bgr = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                except Exception:
                    continue
            elif frame is not None:
                roi = self.rois.get(rois_key)
                if roi is None:
                    continue
                top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
                roi_box = frame[top:bottom, left:right]
                gray_roi = cv2.cvtColor(roi_box.astype("uint8"), cv2.COLOR_BGR2GRAY)
                img = cv2.resize(gray_roi, (target_w, target_h))
                img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            else: 
                continue
            
            # Place in canvas
            canvas[y_start:y_end, x_start:x_end] = img_bgr
            
            # Draw border (green if decoded, red otherwise)
            color = (0, 255, 0) if (rois_key in self.persistent_results and self.persistent_results[rois_key]) else (0, 0, 255)
            cv2.rectangle(canvas, (x_start+1, y_start+1), (x_end-1, y_end-1), color, 2)
        
        cv2.imshow(window_name, canvas)
        cv2.waitKey(1)

    def _get_size_from_images(self, rois_input=None):
        """Get cell size from provided images."""
        if not rois_input:
            return 120, 120
        
        heights, widths = [], []
        for img in rois_input.values():
            if img is not None and img.size > 0:
                h, w = img.shape[:2]
                heights.append(h)
                widths.append(w)
        
        return (max(widths) if widths else 120, max(heights) if heights else 120)

    def _convert_to_bgr(self, img: np.ndarray) -> np.ndarray:
        """Convert image to BGR format."""
        if img.ndim == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 3:
            return img
        else:
            return img[:, :, :3] if img.shape[2] > 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def __process_frame(self, frame, DEBUG_wallet = False):
        """Extract and processes the frame with multiple methods.
        \nMethods: 
            Gray_scale conversion
            Normalization
            Thresholding (if wallet profile)
        """
        ROIs_to_send_decoder = {}   
        for index, roi in self.rois.items():
            # Skip ROIs that are already successfully decoded
            if self.persistent_results.get(index, None):
                continue
            
            top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
            roi_box = frame[top:bottom, left:right]
            gray_roi = cv2.cvtColor(roi_box.astype("uint8"), cv2.COLOR_BGR2GRAY) 
            norm = cv2.normalize(gray_roi, gray_roi, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U) # Stretch contrast: lichtste pixel -> 255, donkerste pixel -> 0

            #! Change bool to test low-contrast wallet thresholds and adaptive thresholds 
            if DEBUG_wallet and self.profile.scan_type == wallet_profile.scan_type:                              
                if self.threshold_value is None: # get threshold value once
                    self.threshold_value = self.test_threshold_values(norm)
                    _, th = cv2.threshold(norm, self.threshold_value, 255, cv2.THRESH_BINARY)
                    cv2.imshow("Wallet ROI threshold", resize_frame(th))
                if self.adaptive_threshold_values is None: # get adaptive threshold values once
                    self.adaptive_threshold_values = self.test_adaptive_threshold_values(norm)
                    th = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, blockSize=self.adaptive_threshold_values[0], C=self.adaptive_threshold_values[1])
                    cv2.imshow("Wallet ROI adaptive threshold", resize_frame(th))
                        
            # store per-index image in dict
            ROIs_to_send_decoder[index] = norm
        return ROIs_to_send_decoder  
    
    def run(self) -> None:
        logger.info("CameraScanner.run started")
        stream_iterator = None
        current_camera_index = self.profile.camera_index
        
        while self.running:
            # Check if camera index changed (profile switch) and reinitialize stream
            if current_camera_index != self.profile.camera_index:
                logger.info(f"Camera index changed from {current_camera_index} to {self.profile.camera_index}, reinitializing stream")
                current_camera_index = self.profile.camera_index
                stream_iterator = None

            # Initialize or reinitialize stream iterator
            if stream_iterator is None:
                stream_iterator = iter(self.streams[self.profile.camera_index])
            try:
                frame = next(stream_iterator) # Get next frame from current stream
            except StopIteration:
                logger.error("Stream ended, reinitializing") # Stream ended, reinitialize it
                stream_iterator = iter(self.streams[self.profile.camera_index])
                break
                
            # Skip processing if 'not running', 'all codes have been detected', 'timeout reached'
            if self.timeout_reached or self.detected_all or self.profile == standard_profile: 
                time.sleep(0.1) #? Reduce CPU usage when timed out or all decoded 
                self.__expire_code_if_needed() # Expire stored code if not collected in main thread
                continue
            
            # If no ROIs assigned yet, try to retrieve them
            if not self.rois and self.profile == giftbox_profile:
                # Always grab a new frame to send to auto roi detection.
                stream_iterator = iter(self.streams[self.profile.camera_index])
                frame = next(stream_iterator)
                if frame is None:
                    continue
                rois = self.__retrieve_rois(frame)
                if rois:
                    self.rois = rois
                    self.profile_switch_time = time.perf_counter()
                else:
                    continue
                     
            # Check if all codes have been decoded
            if len(self.persistent_results) >= len(self.rois):
                self.detected_all = True
                self.codes_retrieved = False
                logger.debug("All ROIs have been successfully decoded.")
                logger.warning(f"Completed in {(time.perf_counter() - self.profile_switch_time)*1000:.4f} milliseconds. \n(time between profile switch and decoded all ROI's)")
                continue
            
            # Check if timeout reached
            if time.perf_counter() - self.profile_switch_time > self.profile.total_timeout:    
                logger.critical(f"Total scan timeout of {self.profile.total_timeout} seconds reached.")
                logger.debug("Please retreive codes or switch profile.")
                self.timeout_reached = True
                if self.codes_retrieved:
                    self.detected_all = True
                self.codes_retrieved = False
            else:
                self.timeout_reached = False

            # Display frames - Before we have results (to show ROI's)
            if self.DEBUG_show_images:
                self.__show_all_rois(frame=frame, display_vertical=True, window_name = "show_normal_grid")
                self.__show_frame(frame)   
                      
            # Wrap the processing in a broad exception catcher so unexpected errors get logged instead of silently terminating the thread.
            try:
                ROIs_to_send_decoder = self.__process_frame(frame) 
                start_time = time.perf_counter()
                self.dm_decoder.decode_datamatrices(ROIs_to_send_decoder) # Send all crops at once
                end_time = time.perf_counter()
                logger.debug(f"Datamatix processing time: {(end_time - start_time)*1000:.3f} milliseconds")

                decoded = self.dm_decoder.get_results()
                # If decoder returned no results or only empty strings (e.g. {1: ''}), treat as no decode and continue to next frame.
                if (not decoded) or (isinstance(decoded, dict) and all(not v for v in decoded.values())):
                    pass
                else:
                    # Sort and save successful decodes to persistent results and log time
                    decoded = dict(sorted(decoded.items()))
                    self.persistent_results |= {roi_idx: value for roi_idx, value in decoded.items() if value}
                    logger.info(f"This round decoded results: {decoded}")  
                    self.code_detected_time = time.perf_counter()        
                                    
            except Exception as e:
                logger.error(f"Exception in camera scanner main loop: {e}")
                break
                                      
            # Display frames - When we have results
            if self.DEBUG_show_images:
                self.__show_all_rois(frame=frame, display_vertical=True, window_name = "show_normal_grid")
                self.__show_all_rois(rois_input=ROIs_to_send_decoder,  window_name = "show_decoder_grid")
                self.__show_frame(frame)         
                      
        # No longer running                
        logger.info("CameraScanner.run exiting")
        print(f"Number of detected codes: {len(self.persistent_results)} / {len(self.rois)}")
        self.persistent_results = dict(sorted(self.persistent_results.items()))
        if len(self.persistent_results) > 0:
            for i in range(1, len(self.rois) + 1):
                print(f"ROI {i:>2}: {self.persistent_results.get(i, '<no code>')}")
        
    def __show_frame(self, frame) -> None:
        """Display the current frame with scaling."""

        final_results = {k: self.persistent_results.get(k, "") for k in self.rois.keys()}
        final_results = dict(sorted(final_results.items()))

        # Draw ROIs on frame
        if frame is not None:
            h, w = frame.shape[:2] 
            for i, roi_box in self.rois.items():
                decoded_str = final_results.get(i, "")
                
                # Draw all ROIs in red and the decoded ROIs in green
                top, bottom, left, right = self.__roi_box_size(h, w, roi_box)
                color = (0, 255, 0) if decoded_str else (0, 0, 255) 
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness=3)
                if decoded_str:
                    cv2.putText(frame, decoded_str, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.6, color, int(4))
            
            # Show image
            cv2.imshow("Camera", resize_frame(frame))
            cv2.waitKey(1)  # in milliseconds
          
    # =====================================================================
    #  Change profile (and camera if needed)
    # =====================================================================
    def switch_profile(self, new_profile: ScanProfile) -> None:
        """Look up a profile by name and switch to it."""
        # Add a check whether the profile is different from the current one
        if self.profile.name == new_profile.name:
            print(f"Already using profile {new_profile.name}, no switch needed.")
            return
        
        logger.info(f"Profile switched from {self.profile.name} to {new_profile.name}, resetting persistent results")
        self.persistent_results.clear()        
        
        if self.profile.camera_index != new_profile.camera_index:
            self.set_active(new_profile.camera_index)
        

        # Apply all profile settings (excluding resolution to avoid MSMF errors)
        self.profile = new_profile
        self.feed_list[self.profile.camera_index].configure_camera(profile=new_profile, set_resolution=False)
        self.__log_profile_settings(self.profile)
        
        # Ensure rois uses the same concrete mapping type as during initialization
        self.rois: dict[int, tuple[int, int, int, int]] = self.profile.rois
        self.profile_switch_time = time.perf_counter()
        self.timeout_reached = False
        self.detected_all = False
        self.codes_retrieved = False

    @staticmethod
    def __log_profile_settings(profile) -> None: 
        """
            Prints the current profile settings to the console.
            Name, type, index, focus, exposure, brightness.
        """
        # Log the change
        print("\n" + "="*50)
        print(f"[PROFILE] Switched to {profile.name} ({profile.scan_type})")
        print(f" Index      -> {profile.camera_index}")
        print(f" Focus      -> {profile.focus}")
        print(f" Exposure   -> {profile.exposure}")
        print(f" Brightness -> {profile.brightness}")
        print("="*50+"\n")
        
    @staticmethod
    def __roi_box_size(h, w, roi_box):
        top, bottom, left, right = roi_box
        # Clip bounds
        top = max(0, min(top, h-1))
        bottom = max(top+1, min(bottom, h))
        left = max(0, min(left, w-1))
        right = max(left+1, min(right, w-1))
        return top, bottom, left, right
    
    @staticmethod
    def test_threshold_values(frame) -> int:
        windowname = "Test Threshold Values"
        cv2.namedWindow(windowname)
        cv2.createTrackbar('ThresholdValue', windowname, 0, 255, nothing)
        
        while True: 
            threshold_value = cv2.getTrackbarPos('ThresholdValue', windowname)
            _, th = cv2.threshold(frame, threshold_value, 255, cv2.THRESH_BINARY)
            cv2.imshow('frame', resize_frame(frame))
            cv2.imshow(windowname, resize_frame(th))
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                break
        cv2.destroyAllWindows()
        print(f"Selected threshold value: {threshold_value}")
        return threshold_value
    
    @staticmethod
    def test_adaptive_threshold_values(frame) -> tuple[int, int]:
        windowname = "Test Threshold Values"
        cv2.namedWindow(windowname)
        cv2.createTrackbar('blocksize value', windowname, 1, 255, nothing) # The blockSize determines the size of the neighbourhood area
        cv2.createTrackbar('c value', windowname, -127, 127, nothing) # C is a constant that is subtracted from the mean or weighted sum of the neighbourhood pixels.
                
        while True: 
            blocksize_value = make_odd(cv2.getTrackbarPos('blocksize value', windowname))
            c_value = cv2.getTrackbarPos('c value', windowname)
            th = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, blockSize=blocksize_value, C=c_value)
            # th = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=blocksize_value, C=c_value)
            cv2.imshow('frame', resize_frame(frame))
            cv2.imshow(windowname, resize_frame(th))
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                break
        cv2.destroyAllWindows()
        print(f"Selected blocksize value: {blocksize_value}, Selected c value: {c_value}")
        return blocksize_value, c_value  

    # ==============================================================
    # Decoders (per profile) and update code
    # ==============================================================
    def __expire_code_if_needed(self) -> None:
        """ Clear `persistent_results` when it has exceeded `profile.data_timeout`. """
        if self.persistent_results:
            elapsed = time.perf_counter() - self.code_detected_time
            if elapsed > (self.profile.data_timeout):
                logger.info(f"Code expired after {elapsed} seconds:")
                self.persistent_results = dict(sorted(self.persistent_results.items()))
                logger.debug(f"Expired the codes: {self.persistent_results}")              
                # for i in range(1, len(self.rois) + 1):
                #     print(f"ROI {i:>2}: {self.persistent_results.get(i, '<no code>')}")
                self.persistent_results = {}

    # Gebruik deze methode voor het ophalen van de laatste code   
    def get_code(self) -> dict[int, str] | None:
        if self.detected_all and not self.codes_retrieved:
            self.codes_retrieved = True
            self.detected_all = False
            return self.persistent_results
        return None
    
    # =====================================================================
    #  Shutdown
    # =====================================================================
    def exit_loop(self) -> None:
        self.running = False
        
