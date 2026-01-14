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
from decoders import DataMatrixDecoder, BarcodeDecoder
from profile_setup import standard_profile, wallet_profile, giftbox_profile, barcode_profile, ScanProfile

# Debugging
from logging_config import set_up_loger
import logging
logger = logging.getLogger()
set_up_loger()

def nothing(x):
    pass

# =====================================================================
#  Camera Scanner
# =====================================================================
class CameraScanner:
    # =================================================================
    #  Initialization
    # =================================================================
    def __init__(self, 
                 dm_decoder: DataMatrixDecoder,
                 barcode_decoder: BarcodeDecoder, 
                 detector: ROIAutoDetector, 
                 feed_list: list,
                 profile: ScanProfile = standard_profile, 
                 debug: bool = False,
                 roi_timeout: float = 5.0) -> None: 
        
        # =============================================================
        # Setting up received parameters
        # =============================================================
        self.dm_decoder = dm_decoder
        self.barcode_decoder = barcode_decoder
        self.detector = detector
        self.feed_list = feed_list
        self.profile: ScanProfile = profile
        self.rois: dict[int, tuple[int, int, int, int]] = profile.rois
        self.DEBUG_show_images: bool = debug
        self.threshold_value: int | None = None
        self.adaptive_threshold_values: tuple[int, int] | None = None
        # =============================================================
        # Setting up starting booleans and values
        # =============================================================
        # Set up feed activity
        self.streams = [f.openFeed() for f in feed_list]
        self.frame_scale = 2
                
        # setting up boolean flags and storage variables
        self.running: bool = True
        self.detected_all: bool = False
        
        # Track when ROI was last changed
        self.roi_transition_time: float = time.time()
        # How many seconds to wait on a ROI without a successful datamatrix decode
        self.roi_timeout: float = float(roi_timeout)
        # Use a dict mapping index -> image to avoid index-assignment errors
        self.ROIs_send_to_decoder: dict[int, object] = {}
           
        # Persistent results across scanning rounds
        self.persistent_results: dict[int, str] = {}  # Results that stay saved (only reset on profile switch)
        # Store last detected timestamp
        self.last_code_time: float = 0
        # Has the last full set of codes been retrieved by caller?
        self.codes_retrieved: bool = False
                
        # Start decoders immediately so they run continuously throughout all frames
        self.dm_decoder.start()
        self.barcode_decoder.start()
        
    def __del__(self) -> None:
        print("Stop Scanner file")
        # Flush any remaining work and stop decoder workers
        try:
            if self.dm_decoder:
                self.dm_decoder.flush()
                self.dm_decoder.stop()
            if self.barcode_decoder:
                self.barcode_decoder.flush()
                self.barcode_decoder.stop()
        except Exception as e:
            logger.error(f"Error stopping decoders: {e}")
            
        # Close camera and all windows
        cv2.destroyAllWindows()
        
    def set_active(self, idx):
        for i, f in enumerate(self.feed_list):
            f.isactive = (i == idx)

    def __retrieve_rois(self, frame) -> dict[int, tuple[int,int,int,int]]:
        try:
            # if self.profile.name != standard_profile.name:
            #     # Temporarily use standard_profile for consistent ROI detection
            #     self.feed_list[self.profile.camera_index].configure_camera(profile=standard_profile, set_resolution=False)
            #     self.profile = standard_profile
            #     time.sleep(0.5)  # small delay for camera to stabilise
            #     return {}
            
            if self.DEBUG_show_images:
                rois = self.detector.capture_loop(frame, max_attempts=2, automatic=True)
            else:
                rois = self.detector.run(frame)    
            if not rois:
                return {}  # Return dummy ROI on failure
            
            # print(f"{len(rois)} ROI's detected, exiting capture loop.")
            cv2.destroyAllWindows()
            # Restore the target profile settings
            self.feed_list[self.profile.camera_index].configure_camera(profile=self.profile, set_resolution=False)
            
            logger.debug(f"Assigned {len(rois)} ROIs from auto-detection for profile {self.profile.name}")
            return rois

        except Exception as e:
            logger.error(f"Auto ROI detection failed in scanner: {e}")
    
        return {}  # Return dummy ROI on failure
    
    def __show_all_rois(self, rois_input=None, frame=None, display_vertical=True, window_name="ROI Grid") -> None:
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
        for i, key in enumerate(ordered_keys):
            if i >= (cols * rows):
                break
            
            # Calculate position
            col = i // rows if display_vertical else i  % cols
            row = i  % rows if display_vertical else i // cols 
            y_start, y_end = row * target_h, (row + 1) * target_h
            x_start, x_end = col * target_w, (col + 1) * target_w
            
            # Get or extract image
            if rois_input is not None:
                img = rois_input.get(key)
                if img is None or img.size == 0:
                    continue
                img_bgr = self._convert_to_bgr(img)
                try:
                    img_bgr = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                except Exception:
                    continue
            elif frame is not None:
                roi = self.rois[key]
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
            color = (0, 255, 0) if (key in self.persistent_results and self.persistent_results[key]) else (0, 0, 255)
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

    def __destroy_profile_windows(self, windows: list[str]) -> None:
        """Destroy any open windows from previous profile."""
        for window in windows:
            try: 
                cv2.destroyWindow(window)
            except cv2.error:
                pass

    def __process_frame(self, frame):
        """Extract and convert current ROI to grayscale."""
        DEBUG_barcode = False
        DEBUG_wallet = False
        if DEBUG_barcode:
            barcode_profile_windows = ["Barcode threshold", "Barcode adaptive threshold"]
            if self.profile.name != barcode_profile.name:
                self.__destroy_profile_windows(barcode_profile_windows)
        if DEBUG_wallet:       
            wallet_profile_windows = ["Selected low-contrast threshold"]
            if self.profile.name != wallet_profile.name:
                self.__destroy_profile_windows(wallet_profile_windows)
            
        for index, roi in self.rois.items():
            # Skip ROIs that are already successfully decoded
            if index in self.persistent_results and self.persistent_results[index]:
                continue
            
            top, bottom, left, right = self.__roi_box_size(frame.shape[0], frame.shape[1], roi)
            roi_box = frame[top:bottom, left:right]
            gray_roi = cv2.cvtColor(roi_box.astype("uint8"), cv2.COLOR_BGR2GRAY) 
            # Stretch contrast: lichtste pixel -> 255, donkerste pixel -> 0
            norm = cv2.normalize(gray_roi, gray_roi, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)  

            if self.profile.name == giftbox_profile.name:
                pass
            
            elif self.profile.name == barcode_profile.name:
                # contrast verbeteren (verscherpen)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                norm  = clahe.apply(norm)
                
                #! Change bool to show thresholded images for debugging
                if DEBUG_barcode:
                    if self.threshold_value is None:
                        self.threshold_value = 128
                        self.threshold_value = self.test_threshold_values(norm) 

                    tresh = cv2.threshold(norm, self.threshold_value, 255, cv2.THRESH_BINARY)[1]
                    if self.DEBUG_show_images:
                        cv2.imshow(barcode_profile_windows[0], tresh)
                    
                    if self.adaptive_threshold_values is None:
                        self.adaptive_threshold_values = (11, 3)  # (blockSize, C)
                        self.adaptive_threshold_value = self.test_adaptive_threshold_values(norm) 
                    blocksize, c = self.adaptive_threshold_values
                    adaptive_tresh = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blocksize, c)
                    if self.DEBUG_show_images:
                        cv2.imshow(barcode_profile_windows[1], adaptive_tresh)
                                
            elif self.profile.scan_type == wallet_profile.scan_type:
                #! Change bool to test low-contrast wallet thresholds and adaptive thresholds 
                if DEBUG_wallet: 
                    test = self.test_low_contrast_wallet(norm, thresh_values=(5, 250, 16), adap_thresh_values=(9, 599, 16), max_per_row=6) # thresh_values and adap_thresh_values are: min, max, amount of steps
                    if self.DEBUG_show_images:
                        cv2.imshow("Selected low-contrast threshold", test)
                
            
            # store per-index image in dict
            self.ROIs_send_to_decoder[index] = norm
            # if self.DEBUG_show_images:
                # cv2.imshow(f"Last ROI send to decoder {index}", norm)
                # cv2.waitKey(1)
            while True:
                if self.profile.scan_type == barcode_profile.scan_type:
                    if self.barcode_decoder.input_queue.full():
                        continue
                    else:
                        self.barcode_decoder.input_queue.put({"index": index, "frame": norm})
                else:
                    if self.dm_decoder.input_queue.full():
                        continue
                    else:
                        self.dm_decoder.input_queue.put({"index": index, "frame": norm})
                break
    
    @staticmethod        
    def normalize_image(img):
        # Normalize using numpy to avoid OpenCV binding/type-check overload issues
        up = img.astype(np.float32)
        minv = float(np.min(up))
        maxv = float(np.max(up))
        span = maxv - minv
        if span <= 0:
            norm = np.clip(up, 0, 255)
        else:
            norm = (up - minv) * (255.0 / span)
        return np.round(norm).astype(np.uint8)
            
    def run(self) -> None:
        print("ESC = quit | f/g = Focus | e/r = Exposure | b/n = Brightness \n")

        logger.info("CameraScanner.run started")
        self.running = True
        # =============================================================
        # Main loop - using while loop to support dynamic camera switching
        # =============================================================
        stream_iterator = None
        current_camera_index = self.profile.camera_index
        self.switch_time = time.time()
        self.timeout_reached = False
        
        while self.running:
            # =============================================================
            # Switch camera stream if profile changed and update frame iterator
            # =============================================================
            # Check if camera index changed (profile switch) and reinitialize stream
            if current_camera_index != self.profile.camera_index:
                logger.info(f"Camera index changed from {current_camera_index} to {self.profile.camera_index}, reinitializing stream")
                current_camera_index = self.profile.camera_index
                stream_iterator = None

            # Initialize or reinitialize stream iterator
            if stream_iterator is None:
                stream_iterator = iter(self.streams[self.profile.camera_index])
            # Get next frame from current stream
            try:
                frame = next(stream_iterator)
            except StopIteration:
                # Stream ended, reinitialize it
                logger.error("Stream ended, reinitializing")
                stream_iterator = iter(self.streams[self.profile.camera_index])
                break
                continue
            
            if self.profile == standard_profile:
                # print("Standard profile selected, skipping scanning.")
                continue
            
            # =============================================================
            # If no ROIs assigned yet, try to retrieve them
            # =============================================================
            if not self.rois and self.profile == giftbox_profile:
                # Always grap a new frame.
                stream_iterator = iter(self.streams[self.profile.camera_index])
                frame = next(stream_iterator)
                if frame is None:
                    continue
                rois = self.__retrieve_rois(frame)
                if rois:
                    print(f"Type = {type(rois)}, Length = {len(rois)}")
                    self.rois = rois
                    self.switch_time = time.time()
                else:
                    continue
                
            self.__handle_key()
                                
            if self.timeout_reached or self.detected_all: 
                time.sleep(0.1) #? Reduce CPU usage when timed out or all decoded 
                self.__expire_code_if_needed() # Expire stored code if not collected
                continue
            
            if len(self.persistent_results) >= len(self.rois):
                self.detected_all = True
                self.codes_retrieved = False
                logger.debug("All ROIs have been successfully decoded.")
                logger.debug(f"Completed in {time.time() - self.switch_time:.4f} seconds.")
                continue
            
            if time.time() - self.switch_time > self.profile.total_timeout:    
                logger.critical(f"Total scan timeout of {self.profile.total_timeout} seconds reached.")
                logger.debug("Please retreive codes or switch profile.")
                self.timeout_reached = True
                self.detected_all = True
                self.codes_retrieved = False
            else:
                self.timeout_reached = False


            total_rois = len(self.rois)
            processing_rois = total_rois - len(self.persistent_results)

            # Display frames - Before we have results (to show ROI's)
            if self.DEBUG_show_images:
                self.__show_all_rois(frame=frame, display_vertical=True, window_name = "show_normal_grid")
                self.__show_all_rois(rois_input=self.ROIs_send_to_decoder,  window_name = "show_decoder_grid")
                self.__show_frame(frame)   
                      
            # Wrap the processing in a broad exception catcher so unexpected errors get logged instead of silently terminating the thread.
            try:
                # Start decoders
                if not self.dm_decoder.active:
                    self.dm_decoder.start()
                if not self.barcode_decoder.active:
                    self.barcode_decoder.start()
                                                                
                t2 = time.perf_counter()
                self.__process_frame(frame) 

                # Decode
                decoded = self.__decode_roi()
                # If decoder returned no results or only empty strings (e.g. {0: ''}), treat as no decode and continue to next frame.
                if (not decoded) or (isinstance(decoded, dict) and all(not v for v in decoded.values())):
                    pass
                else:
                    self.last_code_time = time.time()
                    t3 = time.perf_counter()
                    logger.info(f"Frame decode time: {(t3 - t2):.4f} s")         
                    self.flush_decoder_queues()
                    
                    # Keep decoded as a dict ordered by ROI index (ascending)
                    decoded = dict(sorted(decoded.items()))  # dict(int: str)
                    
                    # Save successful decodes to persistent results
                    self.persistent_results |= {roi_idx: value for roi_idx, value in decoded.items() if value}
                    print(f"Decoded this round: {decoded}")  
                                    
            except Exception as e:
                logger.error(f"Exception in camera scanner main loop: {e}")
                self.dm_decoder.stop()
                self.barcode_decoder.stop()
                break
                                      
            # Display frames - When we have results
            if self.DEBUG_show_images:
                self.__show_all_rois(frame=frame, display_vertical=True, window_name = "show_normal_grid")
                self.__show_all_rois(rois_input=self.ROIs_send_to_decoder,  window_name = "show_decoder_grid")
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

        if frame is not None:
            h, w = frame.shape[:2] 
            for i, roi_box in self.rois.items():
                decoded_str = None
                
                # Draw all ROIs in red, decoded ones in green
                top, bottom, left, right = self.__roi_box_size(h, w, roi_box)
                
                if final_results:    
                    decoded_str = final_results.get(i, "")
                    # print(f"ROI {i+1} decoded string: {decoded_str}")
                color = (0, 255, 0) if decoded_str else (0, 0, 255) 
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness=3)
                if decoded_str:
                    cv2.putText(frame, decoded_str, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8*self.frame_scale, color, int(2*self.frame_scale))
            
            # Show image
            cv2.imshow("Camera", resize_frame(frame))
            cv2.waitKey(1)  # in milliseconds
          
    def __handle_key(self) -> None:
        """Process keyboard input from the capture loop."""          
        key = cv2.waitKey(1) & 0xFF
        if   key == ord('f'): 
            self.configure_feed_camera_properties(self.profile, 'focus', cv2.CAP_PROP_FOCUS, -1)
        elif key == ord('g'): 
            self.configure_feed_camera_properties(self.profile, 'focus', cv2.CAP_PROP_FOCUS, +1)
        elif key == ord('e'): 
            self.configure_feed_camera_properties(self.profile, 'exposure', cv2.CAP_PROP_EXPOSURE, -1)
        elif key == ord('r'):
            self.configure_feed_camera_properties(self.profile, 'exposure', cv2.CAP_PROP_EXPOSURE, +1)
        elif key == ord('b'): 
            self.configure_feed_camera_properties(self.profile, 'brightness', cv2.CAP_PROP_BRIGHTNESS, -1)
        elif key == ord('n'): 
            self.configure_feed_camera_properties(self.profile, 'brightness', cv2.CAP_PROP_BRIGHTNESS, +1)


    def configure_feed_camera_properties(self, profile: 'ScanProfile', attr_name: str, cap_prop: int, delta: float) -> None:
        """Check which feed is currently active and set current_feed accordingly."""
        try: 
            self.feed_list[self.profile.camera_index].adjust_camera_settings(profile, attr_name, cap_prop, delta)
        except Exception as e:
            logger.error(f"Failed to adjust camera property {attr_name}: {e}")

    # =====================================================================
    #  Change profile (and camera if needed)
    # =====================================================================
    def flush_decoder_queues(self) -> None:
        """Flush both decoder queues."""
        self.dm_decoder.flush()
        self.barcode_decoder.flush()

    def switch_profile(self, new_profile: ScanProfile) -> None:
        """Look up a profile by name and switch to it."""
        # Add a check whether the profile is different from the current one
        if self.profile.name == new_profile.name:
            print(f"Already using profile {new_profile.name}, no switch needed.")
            return

        logger.info(f"Profile switched from {self.profile.name} to {new_profile.name}, resetting persistent results")
        self.persistent_results.clear()        
        
        if self.profile.camera_index != new_profile.camera_index:
            # self.current_feed = (self.current_feed + 1) % len(self.feed_list)
            self.set_active(new_profile.camera_index)
        
        self.profile = new_profile

        # Apply all profile settings (excluding resolution to avoid MSMF errors)
        self.feed_list[self.profile.camera_index].configure_camera(profile=new_profile, set_resolution=False)
        self.__log_profile_settings(self.profile)
        
        # Flush decoder queues after camera hardware switch
        self.flush_decoder_queues()
        self.dm_decoder.stop()
        self.barcode_decoder.stop()
        
        # Ensure rois uses the same concrete mapping type as during initialization
        self.rois: dict[int, tuple[int, int, int, int]] = self.profile.rois
        self.switch_time = time.time()
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
        
    # ==============================================================
    # Roi handling
    # ==============================================================
    @staticmethod
    def __roi_box_size(h, w, roi_box):
        top, bottom, left, right = roi_box
        # Clip bounds
        top = max(0, min(top, h-1))
        bottom = max(top+1, min(bottom, h))
        left = max(0, min(left, w-1))
        right = max(left+1, min(right, w-1))
        return top, bottom, left, right
    
    # def test_low_contrast_wallet(self, frame: MatLike, min_adap_thresh_value: int = 9, max_adap_thresh_value: int = 399, adap_thresh_steps: int = 30, max_per_row: int = 18, thumb_h: int = 120, min_thresh_value: int = 95, max_thresh_value: int = 110, thresh_steps: int = 20):
    def test_low_contrast_wallet(self, frame: MatLike, thresh_values, adap_thresh_values, max_per_row: int = 8):
        """Show a set of simple and adaptive threshold variants for `frame`.

        - `min_norm`, `max_norm`, `steps_norm` control the simple (global) thresholds.
        - `min_block`, `max_block`, `steps` control adaptiveThreshold block sizes.
        """
        thumb_h: int = frame.shape[0]
        min_thresh_value, max_thresh_value, thresh_steps = thresh_values
        min_adap_thresh_value, max_adap_thresh_value, adap_thresh_steps = adap_thresh_values
        
        # Normal/global thresholds series
        normal_results = self._threshold_series(frame, mode='normal', min_val=min_thresh_value, max_val=max_thresh_value, steps_norm=thresh_steps)
        im_h1 = self._tile_images(normal_results, max_per_row=max_per_row, thumb_h=thumb_h)
        if im_h1 is not None and getattr(im_h1, 'size', 0) > 0:
            cv2.imshow("All normal Thresholds", im_h1)
        
        # Generate a series of adaptive thresholds between two odd block sizes
        adaptive_results = self._threshold_series(frame, mode='adaptive', min_block=min_adap_thresh_value, max_block=max_adap_thresh_value, steps=adap_thresh_steps, c=3)
        # Show concatenated result and return the finest (smallest blockSize) image
        # adaptive_results is produced in descending block-size order (max -> min)
        im_h2 = self._tile_images(adaptive_results, max_per_row=max_per_row, thumb_h=thumb_h)
        if im_h2 is not None and getattr(im_h2, 'size', 0) > 0:
            cv2.imshow("All adaptive Thresholds", im_h2)
        return normal_results[0]

    def _threshold_series(self, frame: MatLike, mode: str = 'adaptive', *,
                          # adaptive params
                          min_block: int = 9, max_block: int = 399, steps: int = 10, c: int = 5, blocks: list | None = None,
                          # normal params
                          min_val: int = 95, max_val: int = 110, steps_norm: int = 4):
        """Generate a series of threshold images.

        mode: 'adaptive' or 'normal'.
        For adaptive: use min_block/max_block/steps (or explicit `blocks`) and CLAHE constant `c`.
        For normal: use min_val/max_val/steps_norm.
        Returns list of images ordered from largest-parameter -> smallest.
        """
        def make_odd(x: int) -> int:
            x = max(3, int(x))
            return x | 1

        results = []
        if mode == 'adaptive':
            if blocks is not None:
                raw_blocks = [make_odd(int(x)) for x in blocks]
            else:
                lo, hi = int(min_block), int(max_block)
                if lo > hi:
                    lo, hi = hi, lo
                raw = np.linspace(lo, hi, num=steps)
                raw_blocks = [make_odd(int(round(x))) for x in raw]

            uniq = list(dict.fromkeys(raw_blocks))
            uniq.sort(reverse=True)

            for bs in uniq:
                try:
                    results.append(cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, bs, c))
                except Exception:
                    _, th = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                    results.append(th)

        elif mode == 'normal':
            lo, hi = int(min_val), int(max_val)
            if lo > hi:
                lo, hi = hi, lo
            raw = np.linspace(lo, hi, num=steps_norm)
            vals = [int(round(x)) for x in raw]
            vals = list(dict.fromkeys(vals))
            vals.sort(reverse=True)

            for v in vals:
                try:
                    _, th = cv2.threshold(frame, v, 255, cv2.THRESH_BINARY)
                except Exception:
                    _, th = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                results.append(th)

        else:
            raise ValueError(f"Unknown mode for _threshold_series: {mode}")

        return results

    def _tile_images(self, images: list, max_per_row: int = 18, thumb_h: int = 120):
        """Arrange `images` into rows with up to `max_per_row` per row and fixed thumbnail height.

        Returns a single concatenated image (vconcat of hconcat rows) or an empty
        numpy array when input is empty.
        """
        if not images:
            return np.array([])

        # Resize each image to have height `thumb_h` (preserve aspect ratio)
        thumbs = []
        for im in images:
            if im is None or getattr(im, 'size', 0) == 0:
                continue
            h, w = im.shape[:2]
            if h == 0:
                continue
            scale = thumb_h / h
            new_w = max(1, int(round(w * scale)))
            thumbs.append(cv2.resize(im, (new_w, thumb_h)))

        rows = []
        for i in range(0, len(thumbs), max_per_row):
            chunk = thumbs[i:i+max_per_row]
            if len(chunk) == 1:
                rows.append(chunk[0])
            else:
                try:
                    rows.append(cv2.hconcat(chunk))
                except Exception:
                    rows.append(chunk[0])

        if not rows:
            return np.array([])
        if len(rows) == 1:
            return rows[0]

        # Ensure all rows have the same width by padding with black on the right
        widths = [r.shape[1] for r in rows]
        max_w = max(widths)
        padded_rows = []
        for r in rows:
            h, w = r.shape[:2]
            if w < max_w:
                pad_w = max_w - w
                padded = cv2.copyMakeBorder(r, 0, 0, 0, pad_w, cv2.BORDER_CONSTANT, value=0)
                padded_rows.append(padded)
            else:
                padded_rows.append(r)

        return cv2.vconcat(padded_rows)

    @staticmethod
    def test_threshold_values(frame) -> int:
        windowname = "Test Threshold Values"
        cv2.namedWindow(windowname)
        cv2.createTrackbar('ThresholdValue', windowname, 0, 255, nothing)
        
        while True: 
            threshold_value = cv2.getTrackbarPos('ThresholdValue', windowname)
            _, th = cv2.threshold(frame, threshold_value, 255, cv2.THRESH_BINARY)
            cv2.imshow(windowname, resize_frame(th))
            k = cv2.waitKey(1) & 0xFF
            if k == ord('q'):
                break
        cv2.destroyAllWindows()
        print(f"Selected threshold value: {threshold_value}")
        return threshold_value
    
    @staticmethod
    def test_adaptive_threshold_values(frame) -> tuple[int, int]:
        windowname = "Test Threshold Values"
        cv2.namedWindow(windowname)
        # The blockSize determines the size of the neighbourhood area
        cv2.createTrackbar('blocksize value', windowname, 1, 255, nothing)
        # C is a constant that is subtracted from the mean or weighted sum of the neighbourhood pixels.
        cv2.createTrackbar('c value', windowname, -127, 127, nothing)
                
        while True: 
            bs = cv2.getTrackbarPos('blocksize value', windowname)
            bs = 3 if bs <= 1 else bs # min 3
            bs = bs + 1 if bs % 2 == 0 else bs # make odd
            blocksize_value = bs
            c_value = cv2.getTrackbarPos('c value', windowname)
            th = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, blockSize=blocksize_value, C=c_value)
            # th = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=blocksize_value, C=c_value)
            cv2.imshow(windowname, resize_frame(th))
            k = cv2.waitKey(1) & 0xFF
            if k == ord('q'): 
                break
        cv2.destroyAllWindows()
        print(f"Selected blocksize value: {blocksize_value}")
        print(f"Selected c value: {c_value}")
        return blocksize_value, c_value  

    # ==============================================================
    # Decoders (per profile) and update code
    # ==============================================================
    def __decode_roi(self):
        # --- DataMatrix profiles ---
        if self.profile.scan_type == "datamatrix":
            # Wait for all ROI decodes to complete
            return self.dm_decoder.get_results()
        
        # --- Barcode profiles ---
        elif self.profile.scan_type == "barcode":
            return self.barcode_decoder.get_results()
        
        else:
            return {}

    #! Controleren of deze weer werkt
    def __expire_code_if_needed(self) -> None:
        """ Clear `persistent_results` when it has exceeded `profile.data_timeout`. """
        if self.persistent_results:
            elapsed = time.time() - self.last_code_time
            if elapsed > (self.profile.data_timeout):
                logger.info(f"Code expired after {elapsed} seconds:")
                logger.debug("Expired the codes:") # {self.persistent_results}")              
                self.persistent_results = dict(sorted(self.persistent_results.items()))
                for i in range(1, len(self.rois) + 1):
                    print(f"ROI {i:>2}: {self.persistent_results.get(i, '<no code>')}")
                self.persistent_results = {}
    # ==============================================================
    # Others
    # ==============================================================
    # Bastiaan waarom heb ik deze methode?
    def update_state(self, state: str) -> str:
        if (self.state != state):
            logger.info(f"State changed to: {state}")
            self.previous_state = self.state
            self.state = state
        return self.state
    
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
        
